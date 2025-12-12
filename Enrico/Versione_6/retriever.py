import asyncio
import re
import string

from collections import defaultdict
from neo4j_client import Neo4jClient
from resources.auto_queries import AQ
from configuration import sys_labels, config

from language_model import LanguageModel


def clean_string(text: str):
    """
    Clean the string: set all letters to lowercase, delete digits and punctuation
    :param text: the string to be cleaned
    :return: cleaned string
    """
    text = text.lower()  # all lowercase

    text = re.sub(r'\d+', '', text)  # del digits

    # del punctuation
    translator = str.maketrans('', '', string.punctuation)
    text = text.translate(translator)

    return text


def write_list(results: list, item: str = '- ', head: str = '') -> str:
    """
    Print a list
    """
    # TODO: completare la funzione write_list

    message = head

    for element in results:
        element = str(element)
        if element.lower() not in sys_labels:
            message += '\n' + item + element
    return message


def write_dict_of_group(res_dict: dict, head: str = "- § -> ") -> str:
    """
    Print a dictionary with string keys and group-structured values (lists, tuple, etc)
    :param res_dict:
    :param head:
    :return:
    """
    message = ""
    heads = head.split('§')

    if len(heads) < 2:
        print('ERROR: missing heads in dictionary')
        # TODO: controllare la funzione print_dictionary
        return ""

    for key in res_dict.keys():
        if key.lower() in sys_labels:
            continue

        group: list = list(res_dict[key])
        message += '\n' + heads[0] + key + heads[1] + str(group)

    return message


class DataRetriever:

    def __init__(self, client: Neo4jClient, llm_agent: LanguageModel, required_aq: tuple = None, k_lim: int = 10):
        """
        Initialize a DataRetriever that elaborates the database schema
        Args:
            client: Neo4J client to connect the database
            llm_agent: LLM agent, used to analyze the user question
            required_aq: required AutoQueries, execute to get a filtered schema
        """
        self.n4j_cli: Neo4jClient = client
        self.llm_agent: LanguageModel = llm_agent

        self.full_schema = defaultdict(list)  # initial schema
        self.avail_AQ_dict: dict = AQ.global_aq_dict  # import all auto_queries
        self.required_AQs: tuple = self.init_auto_queries(required_aq)  # set required auto-queries
        self.filtered_schema = None  # schema filtered with respect to the question
        self.k_lim = k_lim  # number of elements to retrieve

    async def close(self):
        """
        Close the client
        """
        await self.n4j_cli.close()

    def init_auto_queries(self, required_aq: tuple = None) -> tuple:
        """
        Prepare the tuple with the required auto queries, by verifying that
        they are available
        """
        if required_aq is None:  # all the AQs in the dictionary
            aq_list = self.avail_AQ_dict.keys()
        else:  # only required AQs
            aq_list = []
            for aq_name in required_aq:  # if the required AQ is unavailable
                if aq_name not in self.avail_AQ_dict.keys():
                    print(f'Warning: the query «{str(aq_name)}» is not available')
                    continue
                else:
                    aq_list.append(aq_name)

        return tuple(aq_list)

    async def launch_auto_query(self, auto_query) -> list:
        """
        Launch an automatic query to the Neo4j server.
        :param auto_query: the auto-query to be executed: could be a function or a tuple
            containing function and parameters
        return: a list of results (sometimes with a single element)
        """
        async with self.n4j_cli.driver.session() as session:
            if isinstance(auto_query, tuple):  # query with parameters
                action = auto_query[0]
                params = auto_query[1:]
                return await session.execute_read(action, *params)
            else:  # query without parameters
                return await session.execute_read(auto_query)

    async def init_full_schema(self) -> None:
        """
        Initialize the global (or full) schema in a structured format, in order to filter it.
        """
        all_aq: dict = self.avail_AQ_dict
        initial_AQs: tuple = self.required_AQs

        for aq_name in initial_AQs:  # queries required
            if all_aq[aq_name][AQ.filter_key] == 'exec':
                # these queries must be executed during the filtering only
                continue

            # execute the query
            operation: dict = all_aq[aq_name]
            response: list = await self.launch_auto_query(operation[AQ.func_key])

            self.full_schema[aq_name] = response

    def reset_filter(self):
        self.filtered_schema = self.full_schema.copy()  # dict(list)

    async def dense_filtering(self, results: list[str], question: str, k_lim: int = 10) -> list:
        """
        Filter the schema with respect to the user question
        """
        question_emb = await self.llm_agent.get_embedding(question)
        res_list = []

        for result in results:
            res_emb = await self.llm_agent.get_embedding(result)
            res_sim = self.llm_agent.cosine_similarity(question_emb, res_emb)
            res_list.append((result, res_sim))

        res_list.sort(key=lambda x: x[1], reverse=True)  # ordina per similarità
        out_list = []
        for pair in res_list:
            out_list.append(pair[0])
            if len(out_list) == k_lim:
                break
        return out_list

    async def filter_schema(self, question: str) -> None:
        """
        Filter the schema with respect to the user query
        :param question: user question
        :return: None (update self.filtered_schema)
        """
        aq_map: dict = self.avail_AQ_dict
        full_schema: dict = self.full_schema
        filtered_schema: dict = {}

        for aq_name in self.required_AQs:
            # for each autoquery
            query_params: dict = aq_map[aq_name]

            filter_mode: str = query_params[AQ.filter_key]

            if filter_mode == 'dense':
                filtered_schema[aq_name] = await self.dense_filtering(full_schema[aq_name], question, self.k_lim)
            elif filter_mode == 'exec':
                filtered_schema[aq_name] = await self.launch_auto_query(AQ.global_aq_dict[aq_name][AQ.func_key])
            else:  # == None -> no filtering needed
                filtered_schema[aq_name] = full_schema[aq_name]

        self.filtered_schema = filtered_schema

    def write_schema(self, intro: str = None, filtered: bool = True) -> str:
        """
        Write the (full or filtered) schema to pass it to the LLM
        """
        if filtered:
            chosen_schema = self.filtered_schema
        else:
            chosen_schema = self.full_schema

        if intro is None:
            schema = "\nHere's the database schema:"
        else:
            schema = intro

        executed_aqs = chosen_schema.keys()
        aq_map = self.avail_AQ_dict

        for aq_name in executed_aqs:
            schema += '\n\n'
            operation: dict = aq_map[aq_name]
            response: list[dict] = chosen_schema[aq_name]

            # Heading
            if operation[AQ.head_key] is not None:
                schema += operation[AQ.head_key]
            else:
                schema += aq_name

            # Result printing
            result_key = operation[AQ.results_key]

            if result_key == 'list':
                schema += write_list(response)
            elif result_key == 'list > dict':
                schema += '\n**WIP**' + write_list(response) + '\n**WIP**'
            elif result_key == 'dict > group':
                schema_msg = write_dict_of_group(response[0], head=operation[AQ.text_key])  # type:ignore
                schema += schema_msg
            else:
                schema += '\n' + str(response)

        # TODO: forse conviene creare un attributo per lo schema testuale
        return schema


# Class Identificators
DR = DataRetriever

if __name__ == "__main__":
    import logging

    logging.getLogger("neo4j").setLevel(logging.ERROR)

    test_AQs = config['aq_tuple']  # from configuration
    emb_name = 'nomic-embed-text'
    agent = LanguageModel(embedder_name=emb_name)  # LLM creation
    retriever = DataRetriever(Neo4jClient(password='4Neo4Jay!'),
                              llm_agent=agent,
                              required_aq=test_AQs,
                              k_lim=5)


    async def test_1():
        print("### RETRIEVER TEST 1###", '\n')

        await retriever.init_full_schema()
        print(retriever.write_schema(intro='# FULL SCHEMA #', filtered=False))

        questions = [
            "what is the state of lamp 1?",
            "where is the oven?",
        ]
        question = questions[1]

        await retriever.filter_schema(question=question)
        print('\n', retriever.write_schema(intro=f'# FILTERED SCHEMA # {question} # {emb_name}'))

        await retriever.close()


    async def test_2():
        await retriever.init_full_schema()

        quest = 'Where is the lamp 1?'
        await retriever.filter_schema(question=quest)

        print(retriever.filtered_schema['NAMES'])

        obj_prop_list = await retriever.launch_auto_query(
            auto_query=(AQ.global_aq_dict['OBJECT PROPERTIES'][AQ.func_key], retriever.filtered_schema, 3)
        )
        print(write_list(obj_prop_list, head='Props per object', item='> '))

        await retriever.close()


    asyncio.run(test_2())

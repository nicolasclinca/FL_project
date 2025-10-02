import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

import re
import string

from Enrico.Versione_5.language_model import AgentLLM
from neo4j_client import Neo4jClient
from resources.prompts import AP, QP
from resources.auto_queries import AQ
from configuration import sys_labels, aq_tuple


def clean_string(text: str):
    """
    Clean the string: lower all the characters, delete digits and punctuation
    :param text:
    :type text:
    :return:
    :rtype:
    """
    text = text.lower()  # all lowercase

    text = re.sub(r'\d+', '', text)  # del digits

    # del punctuation
    translator = str.maketrans('', '', string.punctuation)
    text = text.translate(translator)

    return text


def print_list(results: list, head: str = '- '):
    message = ""

    for element in results:
        element = str(element)
        if element.lower() not in sys_labels:
            message += '\n' + head + element
    return message


def print_iterator(result: AsyncIterator):
    # TODO: funzione inutile → eliminare
    # string = ""
    # for record in result:
    #     string += str(record)
    # return string
    pass


def print_dict_of_group(res_dict: dict, head: str = "- # -> "):
    """
    Print a dictionary with string keys and group-structured values (like lists)
    :param res_dict:
    :type res_dict:
    :param head:
    :type head:
    :return:
    :rtype:
    """
    message = ""
    heads = head.split('#')

    if len(heads) < 2:
        print('ERROR: missing heads in dictionary')
        # TODO: controllare la funzione print_dictionary
        return ""

    for key in res_dict.keys():
        if key.lower() in sys_labels:
            continue

        group: list = sorted(list(res_dict[key]))
        message += '\n' + heads[0] + key + heads[1] + str(group)

    return message


class DataRetriever:

    def __init__(self, client: Neo4jClient, agent: AgentLLM, required_aq: tuple = None):
        self.n4j_cli: Neo4jClient = client
        self.llm_agent: AgentLLM = agent

        self.full_schema = defaultdict(list)  # initialize schema
        self.auto_queries_dict = AQ.global_aq_dict  # import all auto_queries
        self.aq_required: tuple = self.init_auto_queries(required_aq)
        self.filtered_schema = None  # filtered with respect to the question

    async def close(self):
        await self.n4j_cli.close()

    def save_json(self):
        schema_dict: dict = self.full_schema
        # TODO: salva il dizionario dello schema in un file json
        pass

    def init_auto_queries(self, required_aq) -> tuple:
        """
        Prepare the tuple with the required auto queries, by verifying that
        they are available
        """
        if required_aq is None:  # all the AQs in the dictionary
            aq_list = self.auto_queries_dict.keys()
        else:  # only required AQs
            aq_list = []
            for aq_name in required_aq:  # if the required AQ is unavailable
                if aq_name not in self.auto_queries_dict.keys():
                    print(f'Warning: the query «{str(aq_name)}» is not available')
                    continue
                else:
                    aq_list.append(aq_name)

        return tuple(aq_list)

    async def launch_auto_query(self, auto_query) -> list:
        """
        Launch an automatic query to the Neo4j server.
        """
        async with self.n4j_cli.driver.session() as session:
            if isinstance(auto_query, tuple):  # query with parameters
                action = auto_query[0]
                params = auto_query[1:]
                return await session.execute_read(action, *params)
            else:  # query without parameters
                return await session.execute_read(auto_query)

    async def init_global_schema(self, save_json: bool = False) -> None:
        """
        Initialize the global (or full) schema in a structured format, in order to filter it.
        """
        all_aq: dict = self.auto_queries_dict
        req_aq: tuple = self.aq_required

        for aq_name in req_aq:  # queries required
            # execute the query
            operation: dict = all_aq[aq_name]
            response: list = await self.launch_auto_query(operation[AQ.func_key])
            # FIXME: response potrebbe non essere sempre una lista → vedremo

            self.full_schema[aq_name] = response

    def reset_filter(self):
        self.filtered_schema = self.full_schema.copy()  # dict(list)

    async def filter_schema(self, question: str) -> None:  # Self.change
        """
        Filter the schema with respect to the user query
        :param question: user question
        :return: None (update self.filtered_schema)
        """
        aq_map = self.auto_queries_dict
        full_schema: dict = self.full_schema
        filtered_schema: dict = {}

        for aq_name in self.aq_required:
            # for each autoquery
            query_data: dict = aq_map[aq_name]

            filter_mode: str = query_data[AQ.filter_key]
            if filter_mode == 'lexical':
                filtered_schema[aq_name] = self.lexical_filtering(full_schema[aq_name], question)
            elif filter_mode == 'node_props':
                filtered_schema[aq_name] = await self.node_props_filtering(full_schema[aq_name], question)
            elif filter_mode == 'dense':
                filtered_schema[aq_name] = await self.dense_filtering(full_schema[aq_name], question)
            else:  # == None -> no filtering needed
                filtered_schema[aq_name] = full_schema[aq_name]

        self.filtered_schema = filtered_schema

    async def node_props_filtering(self, results: list[str], question: str):
        """
        Retrieve all the properties for each object label
        :param results:
        :type results:
        :param question:
        :type question:
        :return:
        :rtype:
        """
        # TODO: node properties filtering
        filtered: list = self.lexical_filtering(results, question)

        all_props: list = []
        for name in filtered:
            node_props: list = await self.launch_auto_query((AQ.node_properties, name))
            node_props: dict = node_props[0]  # type conversion
            all_props.append(node_props)

        return all_props

    @staticmethod
    def lexical_filtering(results: list[str], question: str) -> list:
        question: list = clean_string(" ".join(re.split(r"[_']", question))).split()

        filtered = []
        for result in results:
            if any(word.lower() in question for word in result.split('_')):
                # FIXME: il problema dello split
                filtered.append(result)

        return filtered

    async def dense_filtering(self, results: list[str], question: str, k_lim: int = 10) -> list:
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

    def write_schema(self, intro: str = None, filtered: bool = True) -> str:
        """
        Write the schema to pass it to the LLM
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
        aq_map = self.auto_queries_dict

        for aq_name in executed_aqs:
            schema += '\n\n'
            operation: dict = aq_map[aq_name]
            response = chosen_schema[aq_name]

            # Heading
            if operation[AQ.head_key] is not None:
                schema += operation[AQ.head_key]
            else:
                schema += aq_name

            # Result printing
            result_manager = operation[AQ.results_key]

            if result_manager == 'list':
                schema += print_list(response)
            elif result_manager == 'list > dict':
                schema += '\n**WIP**' + print_list(response) + '\n**WIP**'
            elif result_manager == 'dict > group':
                schema += print_dict_of_group(response[0], head=operation[AQ.text_key])
            else:
                schema += '\n' + str(response)

        # TODO: forse conviene creare un attributo per lo schema testuale
        return schema

    @staticmethod
    def select_instructions(instruction_sel: int = 0):
        if instruction_sel == 1:
            return QP.instruction_pmt_1
        else:  # == 0
            return QP.testing_instructions

    @staticmethod
    def select_ans_pmt(answer_sel: int = 0):
        if answer_sel == 1:
            return AP.answer_pmt_1
        else:  # == 0
            return AP.testing_ans_pmt

    async def init_prompts(self, instr_sel: int = 0, ans_sel: int = 0):
        """
        Initialize the retriever
        :return:
        :rtype:
        """
        question_prompt = self.select_instructions(instr_sel)
        # question_prompt += await self.init_global_schema()

        answer_pmt = self.select_ans_pmt(ans_sel)

        return question_prompt, answer_pmt


# Class Identificators
DR = DataRetriever

if __name__ == "__main__":
    async def test():
        print("### RETRIEVER TEST ###", '\n')

        test_AQs = aq_tuple  # from configuration
        agent = AgentLLM()  # LLM creation
        retriever = DataRetriever(Neo4jClient(password='4Neo4Jay!'),
                                  agent=agent,
                                  required_aq=test_AQs)

        await retriever.init_global_schema()
        # print(retriever.write_schema(intro='# GLOBAL SCHEMA #', filtered=False))

        await retriever.filter_schema(question="what is the state of lamp 1?")
        print('\n\n', retriever.write_schema(intro='# FILTERED SCHEMA #'))

        await retriever.close()


    asyncio.run(test())

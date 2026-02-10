
from collections import defaultdict
import json
# from pprint import pformat

from neo4j_client import Neo4jClient
from auto_queries import AQ
from configuration import sys_labels, config

from language_model import LanguageModel
from embedding_model import Embedder


def write_list(results: list, item: str = '', head: str = '') -> str:
    """
    Print a list
    """

    message = head

    for pair in results:
        element = str(pair[0])
        if element.lower() not in sys_labels:
            message += '\n' + item + element
    return message


def write_list_of_dict(results: list, head: str = '') -> str:
    message = head

    for dictionary in results:
        if not isinstance(dictionary, dict):
            print('ERROR: not a dictionary')
            continue

        dictionary = json.dumps(dictionary, ensure_ascii=False)  # faster
        # dictionary = pformat(dictionary, width=120, compact=True)  # starts with name property

        if dictionary.lower() not in sys_labels:
            message += '\n' + dictionary
    return message


class DataRetriever:

    def __init__(self, n4j_cli: Neo4jClient,
                 # llm_agent: LanguageModel,
                 embedder: Embedder,
                 k_lim: int = 10, thresh: float = 0.65):
        """
        Initialize a DataRetriever that elaborates the database schema
        Args:
            n4j_cli: Neo4J client to connect the database
            llm_agent: LLM agent, used to analyze the user question
        """
        self.n4j_cli: Neo4jClient = n4j_cli
        # self.llm_agent: LanguageModel = llm_agent
        self.embedder: Embedder = embedder

        self.full_schema = defaultdict(list)  # initial schema
        self.global_AQ_dict: dict = AQ.global_aq_dict  # import all auto_queries

        self.required_AQs: tuple = config['aq_tuple']  # set required auto-queries
        self.phases = {
            'init': ('dense-klim', 'dense-thresh', 'dense-both'),
            'filter': ('launch',)
        }



        self.filtered_schema = None  # schema filtered with respect to the question
        self.k_lim = k_lim  # number of elements to retrieve
        self.threshold = thresh  # minimum similarity threshold

    async def close(self):
        """
        Close the client
        """
        await self.n4j_cli.close()

    async def launch_auto_query(self, auto_query: tuple, current_phase: str) -> list:
        """
        Launch an automatic query to the Neo4j server.
        :param auto_query: the auto-query to be executed: could be a function or a tuple
            containing function and parameters
        :param current_phase: Current phase, tells if the query must be executed or not
        return: a list of outputs (sometimes with a single element)
        """

        if current_phase not in self.phases.keys():
            print('Error: phase not recognized')
            return []

        aq_modality = auto_query[1] # from configuration.py
        if aq_modality not in self.phases[current_phase]:
            # Skip current auto-query if not relative to the current phase
            return []

        async with self.n4j_cli.driver.session() as session:
            try:
                aq_name = auto_query[0]
                function = self.global_AQ_dict[aq_name][AQ.function]

                if len(auto_query) > 2:
                    # Query with parameters
                    params = auto_query[2:]
                    return await session.execute_read(function, *params)
                else:
                    # Query without parameters
                    return await session.execute_read(function)
            except Exception as err:
                print(f'{aq_name} is not available! Error: \n{err}\n')
                return []

    async def init_full_schema(self) -> None:
        """
        Initialize the full schema in a structured format, in order to filter it. It includes the embeddings
        """
        for auto_query in self.required_AQs:
            aq_name = auto_query[0] # get AQ name
            # self.global_AQ_dict[aq_name][AQ.filter_mode] = auto_query[1] # set filtering mode for later

            contents = await self.launch_auto_query(auto_query, 'init')
            self.full_schema[aq_name] = await self.embedder.get_list_embeddings(contents)

    def reset_filter(self):
        self.filtered_schema = self.full_schema.copy()  # dict(list)

    async def dense_filtering(self, results: list[tuple], question: str, k_lim: int = 10, thresh: float = 0.65):
        """
        Dense filtering
        """
        question_emb = await self.embedder.get_embedding(question)
        res_list = []

        for result in results:
            res_obj, res_emb = result  # : tuple(object, embedding)
            # res_emb = result # await self.embedder.get_embedding(result)
            res_sim = self.embedder.cosine_similarity(question_emb, res_emb)
            res_list.append((res_obj, res_emb, res_sim))

        # res_list format is (object, embedding, similarity)
        res_list.sort(key=lambda x: x[2], reverse=True)  # sort by descending similarity value
        out_list = []

        for triple in res_list:
            if triple[2] <= thresh:
                break  # when it goes under the minimum threshold
            out_list.append((triple[0], triple[1])) # object and embedding
            if len(out_list) == k_lim:
                break  # when it reaches the k = maximum number of allowed elements
        return out_list

    async def filter_schema(self, question: str) -> None:
        """
        Filter the schema with respect to the user query
        :param question: user question
        :return: None (update self.filtered_schema)
        """
        full_schema: dict = self.full_schema
        filtered_schema: dict = {}

        for auto_query in self.required_AQs:
            aq_name = auto_query[0]
            filter_mode = auto_query[1]

            # query_data: dict = self.global_AQ_dict[aq_name]
            # filter_mode: str = query_data[AQ.filter_mode]

            if filter_mode == 'dense-klim':
                filtered_schema[aq_name] = await (
                    self.dense_filtering(full_schema[aq_name], question, k_lim=self.k_lim, thresh=0))

            elif filter_mode == 'dense-thresh':
                filtered_schema[aq_name] = await (
                    self.dense_filtering(full_schema[aq_name], question, k_lim=0, thresh=self.threshold))

            elif filter_mode == 'dense-both':
                filtered_schema[aq_name] = await (
                    self.dense_filtering(full_schema[aq_name], question, k_lim=self.k_lim, thresh=self.threshold))

            elif filter_mode == 'launch':
                auto_query = list(auto_query)
                auto_query[2] = filtered_schema
                filtered_schema[aq_name] = await self.launch_auto_query(tuple(auto_query), 'filter')
            else:  # == None -> no filtering needed
                filtered_schema[aq_name] = full_schema[aq_name]

        self.filtered_schema = filtered_schema

    def transcribe_schema(self, intro: str = None, filtered: bool = True) -> str:
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

        aq_map = self.global_AQ_dict

        for aq_name in executed_aqs:
            schema += '\n\n'
            operation: dict = aq_map[aq_name]
            response: list[dict] = chosen_schema[aq_name]

            # Heading
            if operation[AQ.text_heading] is not None:
                schema += operation[AQ.text_heading]
            else:
                schema += aq_name

            # Result printing
            result_key = operation[AQ.results_format]

            if result_key == 'list':
                schema += write_list(response)
            elif result_key == 'list > dict':
                schema += write_list_of_dict(response)
            # elif result_key == 'dict > group':
            #     schema_msg = write_dict_of_group(response[0], head=operation[AQ.text_key])  # type:ignore
            #     schema += schema_msg
            else:
                schema += '\n' + str(response)

        return schema


# Class Identificators
DR = DataRetriever

if __name__ == "__main__":
    pass

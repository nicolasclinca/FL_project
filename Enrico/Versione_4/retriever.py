import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

from neo4j_client import Neo4jClient
from resources.prompts import AP, QP
from resources.auto_queries import AQ
from resources.filters import SF

# System labels
sys_classes = ('Resource', 'ObjectProperty', 'DatatypeProperty', 'Ontology',)
sys_rel_types = ('TYPE',)
sys_labels = sys_classes + sys_rel_types


def print_list(results: list, head: str = '- '):
    message = ""

    for result in results:
        result = str(result)
        if result not in sys_labels:
            message += '\n' + head + result
    return message


def print_iterator(result: AsyncIterator):
    # TODO: funzione inutile → eliminare
    # string = ""
    # for record in result:
    #     string += str(record)
    # return string
    pass


def print_dictionary(result: list[dict]):
    pass
    # TODO: scrivere la funzione print_dictionary


class DataRetriever:

    def __init__(self, client: Neo4jClient, required_aq: tuple = None):
        self.client: Neo4jClient = client

        self.schema_structure = defaultdict(list)
        self.auto_queries_dict = AQ.global_aq_dict # import all auto_queries
        self.aq_required: tuple = self.init_auto_queries(required_aq)
        self.filtered_schema = None

    async def close(self):
        await self.client.close()

    def save_json(self):
        schema_dict: dict = self.schema_structure
        # TODO: salva il dizionario dello schema in un file json
        pass

    def init_auto_queries(self, required_aq) -> tuple:
        # Required auto-queries
        if required_aq is None:  # all the possible AQs
            aq_list = self.auto_queries_dict.keys()
        else:  # only required
            aq_list = []
            for aq_name in required_aq:
                if aq_name not in self.auto_queries_dict.keys():
                    print(f'Warning: the query «{str(aq_name)}» is not available')
                    continue
                else:
                    aq_list.append(aq_name)

        return tuple(aq_list)

    async def launch_auto_query(self, auto_query) -> list:
        """
        Launch an automatic query to the Neo4j server.
        :param auto_query:
        :return:
        """
        async with self.client.driver.session() as session:
            if isinstance(auto_query, tuple): # query with parameters
                action = auto_query[0]
                params = auto_query[1:]
                return await session.execute_read(action, *params)
            else: # query without parameters
                return await session.execute_read(auto_query)

    async def init_global_schema(self, save_json: bool = False) -> None:
        """
        Initialize the schema in a structured format, in order to filter it.
        """
        aq_dict = self.auto_queries_dict
        aq_tuple = self.aq_required

        for aq_name in aq_tuple:  # queries required
            # execute the query
            operation: dict = aq_dict[aq_name]
            response: list = await self.launch_auto_query(operation[AQ.query_key])
            # FIXME: response potrebbe non essere sempre una lista → vedremo

            self.schema_structure[aq_name] = response

    def reset_filter(self):
        self.filtered_schema = None

    def filter_schema(self, question: str) -> None: # Self.change
        aq_map = self.auto_queries_dict
        global_schema: dict = self.schema_structure
        filtered_schema: dict = {}

        for aq_name in self.aq_required:
            query_data: dict = aq_map[aq_name]

            if query_data[AQ.filter_key] == 'lexical':
                filtered_schema[aq_name] = SF.lexical_filtering(global_schema[aq_name], question)
            else: # == None
                filtered_schema[aq_name] = global_schema[aq_name]

        self.filtered_schema = filtered_schema
        #pass # TODO: Filter schema


    def write_schema(self, intro: str = None, filtered: bool = True) -> str:
        """
        Write the schema to pass it to the LLM
        """
        if filtered:
            chosen_structure = self.filtered_schema
        else:
            chosen_structure = self.schema_structure

        if intro is None:
            schema = "\nHere's the database schema:"
        else:
            schema = intro


        executed_aqs = chosen_structure.keys()
        aq_map = self.auto_queries_dict

        for aq_name in executed_aqs:
            schema += '\n\n'
            operation: dict = aq_map[aq_name]
            response = chosen_structure[aq_name]

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


# Class Idetificators
DR = DataRetriever


if __name__ == "__main__":
    async def test():
        print("### RETRIEVER TEST ###", '\n')
        aq_tuple = (
            'LABELS',
            # 'PROPERTIES',
            'RELATIONSHIP TYPES',
            # 'RELATIONSHIPS',
            'NAMES',
            # 'GLOBAL SCHEMA',
        )
        retriever = DataRetriever(Neo4jClient(password='4Neo4Jay!'), required_aq=aq_tuple)

        await retriever.init_global_schema()
        print(retriever.write_schema(intro='# GLOBAL SCHEMA #', filtered=False))

        retriever.filter_schema(question='which is the state of television ?')
        print('\n\n', retriever.write_schema(intro='# FILTERED SCHEMA #'))

        await retriever.close()


    asyncio.run(test())

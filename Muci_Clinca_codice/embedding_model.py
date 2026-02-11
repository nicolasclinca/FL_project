import ollama as ol
import numpy as np


class Embedder:
    """
    This is the Embedding model
    """
    def __init__(self, embedder_name: str = None, client: ol.AsyncClient = None):
        """
        Initialize the Embedder class.
        :param embedder_name: The name of the embedding model to use (e.g., 'nomic-embed-text').
        :param client: An optional existing Ollama AsyncClient.
        """
        self.name = embedder_name

        if client is None:
            client = ol.AsyncClient("localhost")
        self.client = client


    def check_installation(self):
        """
        Check if the specified embedding model is installed in Ollama.
        Returns True if installed, False otherwise.
        """
        installed_models = []
        error: bool = False

        for model in ol.list()['models']:
            installed_models.append(model['model'])

        if self.name not in installed_models:
            error = True
            print(f'{self.name} is not installed')

        if error:
            print(f'Installed models are:\n{installed_models}\n')

        return not error

    async def get_embedding(self, text: str) -> np.ndarray:
        """
        Create the embedding of the given text
        """
        response = await self.client.embeddings(model=self.name, prompt=text)
        return np.array(response['embedding'])

    async def get_list_embeddings(self, objects: list[str]) -> list[tuple[str, np.ndarray]]:
        """
        Create an embedding for each element of a list
        """
        output = []
        for content in objects:
            embedding = await self.get_embedding(content)
            output.append((content, embedding))
        return output

    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate the cosine similarity between two vectors.
        :param vec1: First vector.
        :param vec2: Second vector.
        :return: Cosine similarity score (-1 to 1).
        """
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))  # type: ignore
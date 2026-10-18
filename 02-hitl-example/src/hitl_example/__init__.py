import warnings

from langchain_core._api import LangChainBetaWarning

# langchain.mcp and v3 streaming are beta; we opt into both knowingly.
warnings.filterwarnings("ignore", category=LangChainBetaWarning)

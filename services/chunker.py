from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """
    Splits a large string of text into overlapping chunks of a specified token size
    using LangChain's RecursiveCharacterTextSplitter with tiktoken encoding.
    """
    # Use the gpt-3.5-turbo standard encoding which works well generally
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        model_name="gpt-3.5-turbo",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    chunks = text_splitter.split_text(text)
    return chunks

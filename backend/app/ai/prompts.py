from langchain_core.prompts import ChatPromptTemplate

EXTRACTION_PROMPT_TEMPLATE = """
You are an expert industrial product data extractor.
Your task is to extract product attributes from the given product information and retrieved evidence snippets.

Product Information:
{product_info}

Retrieved Evidence Snippets:
{evidence_text}

Instructions:
1. Extract the attributes requested by the schema.
2. The LLM must ground each attribute strictly in the retrieved evidence snippets.
3. If an attribute is not present in the evidence or has insufficient support, set its value to null and status to "UNKNOWN" or "REQUIRES_REVIEW".
4. If an attribute is supported by the evidence, set its status to "EXTRACTED".
5. Every extracted attribute MUST list the exact evidence IDs from the retrieved evidence snippets that support it.
6. Do NOT fabricate or assume information not present in the evidence.

Return STRICT JSON adhering to the provided schema.
"""

EXTRACTION_PROMPT = ChatPromptTemplate.from_template(EXTRACTION_PROMPT_TEMPLATE)

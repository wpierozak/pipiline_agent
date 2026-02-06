# Embeddings Module

## Overview

The `embeddings` module provides semantic and lexical text matching using embedding models. It combines fuzzy string matching with embedding-based similarity to align queries with registered phrases, making it ideal for correcting misspellings or finding semantically similar text.

## Classes

### AlignerPool

A pool of phrases with dual matching strategies: lexical (fuzzy string matching) and semantic (embedding similarity).

**Constructor Parameters:**
- `lexical_threshold` (float): Threshold for fuzzy matching (0-100 scale internally)
- `semantic_threshold` (float): Threshold for embedding similarity (0-1 scale)

**Key Methods:**

#### `add(model: TextEmbedding, phrase: str)`
Adds a phrase to the pool with its embedding vector.

**Parameters:**
- `model` (TextEmbedding): Embedding model to generate vectors
- `phrase` (str): Phrase to register

#### `match(model: TextEmbedding, query: str) -> str | None`
Matches a query against registered phrases using a three-tier strategy:

1. **Exact Match**: Returns immediately if query exactly matches a phrase
2. **Lexical Match**: Uses fuzzy string matching (rapidfuzz) against threshold
3. **Semantic Match**: Uses embedding cosine similarity against threshold

**Parameters:**
- `model` (TextEmbedding): Embedding model for query encoding
- `query` (str): Query string to match

**Returns:**
- Matched phrase if found, None otherwise

**Matching Strategy:**
The pool tries matches in order of decreasing precision:
1. Exact string match (cheapest)
2. Fuzzy match (fast approximation)
3. Semantic match (most accurate but expensive)

**Example Usage:**
```python
from pipiline_agent.embeddings.aligner import AlignerPool
from fastembed import TextEmbedding

model = TextEmbedding("BAAI/bge-small-en-v1.5")

pool = AlignerPool(
    lexical_threshold=90.0,    # 90% similarity for fuzzy matching
    semantic_threshold=0.75     # 0.75 cosine similarity for embeddings
)

# Register phrases
pool.add(model, "create_script")
pool.add(model, "run_script")
pool.add(model, "delete_file")

# Match queries
print(pool.match(model, "create_script"))   # Exact: "create_script"
print(pool.match(model, "creat_script"))    # Lexical: "create_script"
print(pool.match(model, "make a script"))   # Semantic: "create_script"
print(pool.match(model, "xyz123"))          # None
```

---

### Aligner

Main interface for managing multiple alignment pools and performing phrase matching.

**Constructor Parameters:**
- `model_name` (str, default="BAAI/bge-small-en-v1.5"): Embedding model name
- `threads` (int, default=1): Number of threads for embedding model

**Key Methods:**

#### `create_pool(name: str, lexical_threshold: float = 90.0, semantic_threshold: float = 0.75) -> AlignerPool`
Creates a new alignment pool.

**Parameters:**
- `name` (str): Unique identifier for the pool
- `lexical_threshold` (float): Fuzzy matching threshold (0-100)
- `semantic_threshold` (float): Embedding similarity threshold (0-1)

**Returns:**
- Created `AlignerPool` instance

**Raises:**
- `RuntimeError`: If pool with same name already exists

#### `get_pool(name: str) -> AlignerPool`
Retrieves an existing pool.

**Parameters:**
- `name` (str): Pool identifier

**Returns:**
- The requested `AlignerPool`

**Raises:**
- `RuntimeError`: If pool doesn't exist

#### `add_phrase(pool_name: str, phrase: str)`
Adds a phrase to a specific pool.

**Parameters:**
- `pool_name` (str): Target pool name
- `phrase` (str): Phrase to add

**Raises:**
- `RuntimeError`: If pool doesn't exist

#### `match(pool_name: str, query: str) -> str | None`
Matches a query against phrases in a specific pool.

**Parameters:**
- `pool_name` (str): Pool to search in
- `query` (str): Query string

**Returns:**
- Matched phrase or None

**Raises:**
- `RuntimeError`: If pool doesn't exist

**Example Usage:**

**Basic Matching:**
```python
from pipiline_agent.embeddings.aligner import Aligner

aligner = Aligner(model_name="BAAI/bge-small-en-v1.5", threads=2)

# Create a pool for tool names
tools_pool = aligner.create_pool(
    "tools",
    lexical_threshold=85.0,
    semantic_threshold=0.7
)

# Register tool names
aligner.add_phrase("tools", "create_file")
aligner.add_phrase("tools", "delete_file")
aligner.add_phrase("tools", "read_file")

# Match queries
print(aligner.match("tools", "create_file"))      # "create_file"
print(aligner.match("tools", "crete_file"))       # "create_file" (typo)
print(aligner.match("tools", "make a new file"))  # "create_file" (semantic)
```

**Multiple Pools:**
```python
# Create separate pools for different domains
aligner.create_pool("commands", lexical_threshold=90.0)
aligner.create_pool("arguments", lexical_threshold=95.0, semantic_threshold=0.8)

# Add phrases to each pool
aligner.add_phrase("commands", "execute")
aligner.add_phrase("commands", "terminate")

aligner.add_phrase("arguments", "timeout")
aligner.add_phrase("arguments", "max_retries")

# Match in specific pools
aligner.match("commands", "exec")       # "execute"
aligner.match("arguments", "time_out")  # "timeout"
```

**Tool Name/Argument Alignment:**
```python
aligner = Aligner()

# Pool for tool names
aligner.create_pool("tool_names", lexical_threshold=90.0)
aligner.add_phrase("tool_names", "create_script")
aligner.add_phrase("tool_names", "run_script")

# Pool for create_script arguments
aligner.create_pool("create_script_args", lexical_threshold=95.0)
aligner.add_phrase("create_script_args", "relative_path")
aligner.add_phrase("create_script_args", "content")

# Align misspelled tool call
tool_name = aligner.match("tool_names", "creat_scrpt")  # "create_script"
arg_name = aligner.match("create_script_args", "rel_path")  # "relative_path"
```

## Use Cases

### Misspelling Correction

Correct user input or LLM-generated text with typos:

```python
aligner = Aligner()
aligner.create_pool("cities")
aligner.add_phrase("cities", "San Francisco")
aligner.add_phrase("cities", "New York")

# Handles typos
aligner.match("cities", "San Fransisco")  # "San Francisco"
aligner.match("cities", "New Yrok")       # "New York"
```

### Semantic Search

Find semantically similar phrases:

```python
aligner = Aligner()
aligner.create_pool("actions", semantic_threshold=0.6)
aligner.add_phrase("actions", "delete")
aligner.add_phrase("actions", "create")
aligner.add_phrase("actions", "update")

aligner.match("actions", "remove")     # "delete"
aligner.match("actions", "make")       # "create"
aligner.match("actions", "modify")     # "update"
```

### Tool Call Alignment

Correct LLM tool calls with misspelled names/arguments (see [chat.ToolAligner](../chat/README.md)):

```python
aligner = Aligner()
aligner.create_pool("tools")
aligner.add_phrase("tools", "PythonWorkSpace.create_script")

# LLM makes a typo
corrected = aligner.match("tools", "PythonWorkSpace.creat_script")
# Returns: "PythonWorkSpace.create_script"
```

## Matching Thresholds

### Lexical Threshold (0-100)

Controls fuzzy string matching sensitivity:
- **95-100**: Very strict, only minor typos
- **85-95**: Moderate, handles common misspellings
- **70-85**: Lenient, accepts significant variations
- **<70**: Very lenient, may produce false positives

### Semantic Threshold (0-1)

Controls embedding similarity:
- **0.8-1.0**: Very strict, nearly identical meaning
- **0.7-0.8**: Moderate, similar concepts
- **0.5-0.7**: Lenient, related concepts
- **<0.5**: Very lenient, loosely related

## Performance Considerations

- **Exact matching**: O(1) lookup, no computation
- **Lexical matching**: O(n) fuzzy comparison, fast
- **Semantic matching**: Requires embedding generation, slower but most accurate
- **Memory**: Stores embedding vectors for all phrases

**Optimization Tips:**
- Use higher lexical thresholds to reduce semantic matching calls
- Cache Aligner instances to avoid re-loading embedding models
- Use multiple specialized pools instead of one large pool

## Dependencies

- `numpy` - Vector operations
- `fastembed` - Embedding model (TextEmbedding)
- `rapidfuzz` - Fuzzy string matching (process, fuzz)
- `logging` - Debug logging for match scores

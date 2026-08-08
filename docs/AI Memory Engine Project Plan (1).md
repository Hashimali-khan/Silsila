# **Architectural Blueprint for a Multi-Source AI Memory Engine: Conversation Reconstruction and Persistent Memory**

## **Executive Summary**

The transition from a basic chat analysis utility to a comprehensive "AI Memory Engine" represents a paradigm shift in personal data retrieval and knowledge synthesis. Historically, attempts to recover past conversational data have been constrained by exact-match search paradigms or naive semantic vector searches. Both fail when applied to human relationships.  
Users do not recall precise wording or isolated chunks of text. They remember a continuous story. A system built purely on vector search evaluates messages as isolated islands of data. It cannot understand that an ambiguous text like "acha..." or a single "👍🏻" emoji can drastically change meaning (from comfort to sarcasm to anger) depending on the relationship context established 4,000 messages prior.  
The proposed architectural blueprint outlines a **Conversation Reconstruction Engine**. Rather than relying on a simple "Search ![][image1] Retrieve ![][image1] Answer" pipeline, this system utilizes a "Conversation ![][image1] Context ![][image1] Memory ![][image1] Timeline ![][image1] Understanding ![][image1] Evidence ![][image1] Answer" flow. By building a Persistent Conversation Memory via a structured Knowledge Graph, the AI tracks aliases, temporal shifts, and relationship states, allowing it to act as a relationship detective that reconstructs conversational timelines backed by verifiable evidence.

## **The Problem Statement and Core Vision**

The fundamental limitation of current AI RAG (Retrieval-Augmented Generation) systems is the "Isolated Chunk Problem"1. When an LLM evaluates a conversational export, splitting it into text chunks destroys the causal chains and temporal knowledge embedded in the discourse1.  
For example, consider how humans use aliases:

> 1. Two months ago, a conversation establishes that "wo" refers to Abdullah.  
> 2. A week later, neither person uses the name Abdullah, but both understand that "wo" still means Abdullah.

A standard vector database cannot resolve this because the meaning is carried through the relationship's memory, not the individual message. Furthermore, if a user asks a reasoning question like, "Trace every connection of Abdullah," a standard search engine will fail. Answering this requires knowing his aliases, understanding the chronology of his appearances and disappearances, recognizing indirect references, and evaluating the relationship state at different points in time1.  
The core vision of this engine is not to search messages or guess what people were thinking, but to **reconstruct the conversation from evidence** and present the chain of messages that support its conclusions.

## **The Intelligence Pipeline: Memory over Embeddings**

To achieve true relationship understanding, the underlying architecture must be inverted. Embeddings and vector search are no longer the center of the application; the **Memory Graph** is.  
The data flows through a heavily structured, relationship-first pipeline:**Import ![][image1] Parser ![][image1] Conversation Threads ![][image1] Events ![][image1] People ![][image1] Topics ![][image1] Memory Graph ![][image1] Embeddings ![][image1] Hybrid Search ![][image1] Evidence Builder ![][image1] LLM**

> 1. **Import & Parser:** The ingestion layer remains agnostic. Whether reading a WhatsApp .txt file or an iMessage SQLite database, it normalizes the raw data into a standard interface.  
> 2. **Context Structuring (Threads, Events, People, Topics):** Before any vector math occurs, the system identifies continuous conversation threads, extracts temporal events, resolves aliases via coreference resolution, and tags ongoing topics4.  
> 3. **The Memory Graph:** This structured data is written into a relational graph representing the Persistent Conversation Memory.  
> 4. **Embeddings & Hybrid Search:** Vector embeddings are generated strictly to act as a supplementary fuzzy-matching index for the structured graph6.  
> 5. **Evidence Builder:** The retrieval system traverses the graph to collect a chronological, multi-hop evidence trail before the LLM generates an answer7.

## **The Memory Graph: Persistent Conversation Memory**

Standard RAG over raw transcripts retrieves text, not knowledge8. To solve the accumulated context problem, the engine requires a structure capable of relationship-aware, temporally-versioned retrieval8. This is achieved using GraphRAG architecture natively within PostgreSQL.  
Instead of deploying a separate graph database which adds massive synchronization overhead, the system leverages PostgreSQL's native ability to traverse graphs using SQL Recursive Common Table Expressions (CTEs)9.  
Every person, event, and topic becomes a node. Every relationship ("mentioned", "argued with", "ghosted after") becomes an edge1. When the system maps a timeline:

* *Abdullah* (Appears first) ![][image1] *Abdullah* (Starts becoming frequent) ![][image1] *Conversation changes* ![][image1] *Indirect references ("wo") begin* ![][image1] *Stops appearing*.

This Memory Graph tracks these changes perpetually. When the user asks, "Why did this joke become funny?", the system doesn't just look for similar keywords; it executes a recursive CTE to walk backward through the relationship edges, finding the exact multi-hop chain of events that originated the joke 4,000 messages earlier1.

### **Entity Extraction and Alias Disambiguation**

Building this graph requires robust, zero-shot entity extraction at the ingestion phase. The pipeline utilizes GLiNER (Generalist and Lightweight Model for Named Entity Recognition), a highly efficient bidirectional transformer that extracts entities without needing predefined labels11.  
As GLiNER processes the text, conversational coreference resolution algorithms map shifting pronouns ("he", "wo", "usne") to their canonical entity IDs2. This ensures the Memory Graph maintains a single, persistent identity for a person, regardless of the nickname used in a specific message.

## **The Evidence Builder and Hybrid Search**

While the Memory Graph provides the structural and temporal reasoning, it is paired with Hybrid Search to capture semantic nuances. The system utilizes pgvector for dense semantic search and PostgreSQL's tsvector for exact keyword matches. The results from the vector and text searches are merged using Reciprocal Rank Fusion (RRF), a mathematical formula that combines disparate ranking scales into a single, highly accurate retrieval list14.  
![][image2]

### **Conversation Reconstruction**

The Hybrid Search and the Memory Graph converge in the **Evidence Builder**. When a user asks an investigative question ("When did our dynamic start changing?"), the Evidence Builder initiates a multi-hop traversal6.  
Rather than passing a chaotic pile of text chunks to the LLM, the Evidence Builder constructs a deterministic, auditable retrieval trail7. It hands the LLM a chronological sequence of events, verified aliases, and relationship states, alongside the exact messages. The LLM then synthesizes this data, citing the explicit graph paths and source messages, guaranteeing that the AI answers by reconstructing the conversation from hard evidence rather than hallucinating intent6.

## **Database Architecture**

To support this graph-first approach without external dependencies, the centralized PostgreSQL database utilizes a highly relational schema:

| Table Name | Primary Purpose |
| :---- | :---- |
| Messages | The central storage for all parsed communications, including attachments and emojis. |
| People & Aliases | Unique identities and their resolved nicknames. The nodes of the Memory Graph. |
| Events | System-detected temporal occurrences (fights, birthdays, ghosting). |
| Relationships | Graph edges mapping the connections between People and Events, traversable via Recursive CTEs. |
| Conversation Threads | Logically grouped reply chains required for contextualizing short messages (e.g., "acha"). |
| Embeddings | Stores the high-dimensional vector representation (halfvec) of the message content for hybrid search. |

## **Security and Defense Against Embedding Inversion**

Because this system ingests a user's entire digital life, privacy is paramount. A critical danger in modern AI architectures is the misconception that vector embeddings are one-way cryptographic hashes. In reality, embeddings are specifically designed to preserve semantic meaning and are highly vulnerable to Embedding Inversion Attacks17.  
Malicious actors can use gradient-based optimization or trained decoder networks to reconstruct the exact original plaintext of a conversation directly from the mathematical vector, exposing highly sensitive personal histories17.  
To secure the Memory Engine, the architecture implements the SPARSE framework, a sensitivity-guided differential privacy mechanism. Unlike standard noise injection which destroys the utility of the vectors, this mechanism utilizes differentiable mask learning to identify which specific dimensions encode sensitive attributes. It then selectively perturbs those dimensions using the Mahalanobis mechanism21. This ensures the vectors remain highly accurate for semantic retrieval while cryptographically guaranteeing that raw conversational text cannot be mathematically reconstructed by an attacker21.

## **Strategic Phased Implementation Roadmap**

| Phase | Title | Core Objectives and Deliverables |
| :---- | :---- | :---- |
| **Phase 1** | **Foundations** | Construct the PostgreSQL schema. Build the universal parser. Implement basic file uploading, raw data ingestion, and Conversation Threads grouping. |
| **Phase 2** | **Memory Graph Generation** | Deploy GLiNER for zero-shot entity extraction. Implement coreference and alias resolution. Begin mapping chronological Events and People into graph nodes and edges. |
| **Phase 3** | **AI Search & Hybrid Retrieval** | Integrate pgvector and HNSW indexing. Construct the hybrid semantic/lexical search pipeline (Reciprocal Rank Fusion). |
| **Phase 4** | **The Evidence Builder** | Implement SQL Recursive CTEs for multi-hop graph traversal. Combine graph paths with hybrid search to build the Evidence Builder, enabling verifiable Conversation Reconstruction. |
| **Phase 5** | **Multi-source Memory** | Expand parser connectors beyond WhatsApp. Integrate Discord, Instagram DMs, Telegram, and Emails, ensuring the entity resolution engine merges cross-platform identities into a single Persistent Memory. |
| **Phase 6** | **Product & Privacy** | Harden the application for production. Apply differential privacy noise to protect against Embedding Inversion. Develop secure export features and multi-tenant workspaces. |

## **Conclusion**

Building a true AI Memory Engine requires abandoning the industry-standard, flat-vector RAG playbook. Human relationships and conversations are not isolated data chunks; they are continuous, highly contextual webs of meaning where a single word or emoji relies on months of historical precedent.  
By centering the architecture on a Persistent Conversation Memory—powered by a native PostgreSQL Knowledge Graph, alias disambiguation, and recursive traversal—the engine stops merely searching for words. Instead, it utilizes hybrid retrieval and an Evidence Builder to trace chronological and relational evidence. This allows it to answer profound reasoning questions about a user's life history with complete transparency, transforming fragmented chat logs into a coherent, reconstructed narrative.

#### **Works cited**

> 1. Knowledge Graph RAG: How to Build AI Systems That Understand Relationships, Not Just Words | atal upadhyay, [https://atalupadhyay.wordpress.com/2026/03/06/knowledge-graph-rag-how-to-build-ai-systems-that-understand-relationships-not-just-words/](https://atalupadhyay.wordpress.com/2026/03/06/knowledge-graph-rag-how-to-build-ai-systems-that-understand-relationships-not-just-words/)  
> 2. Agentic GraphRAG: Navigating Unstructured Financial Data with Collaborative AI \- arXiv, [https://arxiv.org/html/2605.18770v1](https://arxiv.org/html/2605.18770v1)  
> 3. Graph-augmented RAG patterns in Azure HorizonDB (Preview) \- Microsoft Learn, [https://learn.microsoft.com/en-us/azure/horizondb/ai/graph-rag](https://learn.microsoft.com/en-us/azure/horizondb/ai/graph-rag)  
> 4. Coreference Resolution and Entity Linking \- Stanford University, [https://web.stanford.edu/\~jurafsky/slp3/26.pdf](https://web.stanford.edu/~jurafsky/slp3/26.pdf)  
> 5. A Unified Approach to Entity-Centric Context Tracking in Social Conversations \- ACL Anthology, [https://aclanthology.org/2022.lrec-1.136.pdf](https://aclanthology.org/2022.lrec-1.136.pdf)  
> 6. RAG vs GraphRAG: When the Vector Database Stops Being Enough \- Cognilium AI, [https://cognilium.ai/blogs/rag-vs-graphrag](https://cognilium.ai/blogs/rag-vs-graphrag)  
> 7. Graph RAG vs Vector RAG: How to Choose the Right Retrieval Strategy \- Airbyte, [https://airbyte.com/agentic-data/graph-rag-vs-vector-rag](https://airbyte.com/agentic-data/graph-rag-vs-vector-rag)  
> 8. Scaling Agent Context with Knowledge Graphs on Snowflake | Capital One Software, [https://capitalonesoftware.com/blog/scaling-agent-context-snowflake-knowledge-graphs](https://capitalonesoftware.com/blog/scaling-agent-context-snowflake-knowledge-graphs)  
> 9. A Python Library to perform Graph RAG in your Postgres DB without headaches \- GitHub, [https://github.com/h4gen/postgres-graph-rag](https://github.com/h4gen/postgres-graph-rag)  
> 10. Postgres as a Graph Database: Four Approaches Compared \- Evokoa, [https://evokoa.com/blog/postgres-as-a-graph-database/](https://evokoa.com/blog/postgres-as-a-graph-database/)  
> 11. GLiNER \- Zero Shot NER Framework \- EveryDev.ai, [https://www.everydev.ai/tools/gliner](https://www.everydev.ai/tools/gliner)  
> 12. GLiNER for Modern Named Entity Recognition \- Pioneer AI by Fastino Labs, [https://pioneer.ai/blog/gliner-modern-named-entity-recognition](https://pioneer.ai/blog/gliner-modern-named-entity-recognition)  
> 13. Robust Coreference Resolution and Entity Linking on Dialogues: Character Identification on TV Show Transcripts, [https://aclanthology.org/K17-1023.pdf](https://aclanthology.org/K17-1023.pdf)  
> 14. Hybrid Search Using Reciprocal Rank Fusion in SQL \- SingleStore, [https://www.singlestore.com/blog/hybrid-search-using-reciprocal-rank-fusion-in-sql/](https://www.singlestore.com/blog/hybrid-search-using-reciprocal-rank-fusion-in-sql/)  
> 15. Hybrid Search with pgvector and PostgreSQL Full-Text Search \- Rivestack, [https://rivestack.io/blog/hybrid-search-pgvector-postgres](https://rivestack.io/blog/hybrid-search-pgvector-postgres)  
> 16. Microservices, Cloud Native and AI | Page 2 \- RedStack, [https://redstack.dev/page/2/](https://redstack.dev/page/2/)  
> 17. Embedding Inversion Attacks \- Emergent Mind, [https://www.emergentmind.com/topics/embedding-inversion-attacks](https://www.emergentmind.com/topics/embedding-inversion-attacks)  
> 18. Vector Embedding Inversion: Reconstructing Sensitive Data from Embeddings | AquilaX, [https://aquilax.ai/blog/vector-embedding-inversion-attacks](https://aquilax.ai/blog/vector-embedding-inversion-attacks)  
> 19. Embedding Inversion \+ Encrypted Vector DB: The Future of Privacy-Aware RAG \- Medium, [https://medium.com/@himansusaha/embedding-inversion-encrypted-vector-db-the-future-of-privacy-aware-rag-e0caf0985ee1](https://medium.com/@himansusaha/embedding-inversion-encrypted-vector-db-the-future-of-privacy-aware-rag-e0caf0985ee1)  
> 20. Transferable Embedding Inversion Attack: Uncovering Privacy Risks in Text Embeddings without Model Queries \- arXiv, [https://arxiv.org/html/2406.10280v1](https://arxiv.org/html/2406.10280v1)  
> 21. Concept-Aware Privacy Mechanisms for Defending Embedding Inversion Attacks \- arXiv, [https://arxiv.org/pdf/2602.07090](https://arxiv.org/pdf/2602.07090)  
> 22. Concept-Aware Privacy Mechanisms for Defending Embedding Inversion Attacks \- arXiv, [https://arxiv.org/html/2602.07090v1](https://arxiv.org/html/2602.07090v1)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAZCAYAAADe1WXtAAAAfklEQVR4XmNgGAWjYMCBHBD3ADEHugQlQACINwGxFroEpaACiqkOzIFYFV0QGfACsRQZ+C4QpwAxJwMWUMkAUUAq/g3ET4A4kYFKgAeI+xlwuJIcwArE04CYEV2CXAAycBEQe6JLUAJkGCDpVBRdghIAcqkQAxW9PgpGAQEAAHTFFrHB+82xAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAABUCAYAAAA/I2vMAAAK1klEQVR4Xu3da4h1VR3H8X9UkJpZ2Z2I6WoXK+whK18kRAURVEoXkyzf9KKwJAqKCJJCIgtKSijCmArJ7iFldsUuL5TMrgRlF4ksoSwqgqKg1td1/s9es2afOZe5nZn5fmDxzNl7nX3OHIXzm/+67AhJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiTpiDmhtBeWdlNp/538LEmSpBVyn9LeXdo5pX0vDGySJEkr6+TSvhUGNkmSpJVlYJMkSVpxBjZJkqQVZ2CTJEkr5bml/XqH2jVxOBjYJEnSSjm9tP9N2nWlvay0l87RPlraD5rn0v4Vh4OBTZIkrZyPxBC6ftSdm9ebS/t7aU/sTxxABjZJko6YR5f2zf7gFHcv7fWl3aU/sQeeFkNoO687t4jrS3tQf/CAyKDWVg1pBjdJ0kq7f2nnxubhsGdF/XLr0b/vm/3HTOvfNkLMQXZzaS/pDzaeU9pFUTdsZePWr0WtVu0HdvcnoNxe2rHu3LzeWdpr+4OSJGn3/aO0PzSPqQBRheGLvffMqP0f3xyj/z9jvD+T3pn79NTu+ONK+3mMB8OD4pVRK2yzXFDaByY/81ldWtoDh9N7Zi3qZ56Vpf2o9EmSpCXx5f3t7ti9Jsd7r4l6nPMtnj/W/y1Rj1Nd6r2rP3CAnFraDTFf6LmytBc3j5kHtl9VKgJ0BratKoOSJGmFMGzJl3cbKHDW5HjvxzF+/G8xfvyW2HicyhzDsCDMHVTrUT+LWc4o7U+xOeDeEZurjnvl6zGEtsOyVYckSYcaoYHh0H6I84qoX+w9gkY7fAr68+U/1r8fbqWqRpUOT2qOz+OupT096qrHV3Tn8Nioc6xeXdop3TkqYjzvPTFUxe5Z2sVRh2fBcznfeljU9/v2yc+JsPbZ5nGL63MthkEZNh0LsgwT5+ew1xjGvTXq+2Je2zxVQkmStE/4ol4v7ZdRw8ynJj9fGzUY9TKYtf3Z6oH+Y1/694janz5svPqbqEGHqt4yuMYjos7/+n5pD5kcP7O020q77+QxP1Pxw72jzq1jlWQiLFFRJHCdEPU9MreL4ULm4lEVW5scyzlqLI5oAxpBZ6xCSGht5/LxWn3Axa9K+1J/cILP7WOxeePascbnsAx+n6yy/bS0h248LUmSVgXBiQB1YdTwc1rUIHZ11KDTy+HTC2Po/++o/ccQAuh/WdQVoZeUdlWMh7tZTooaLNhSYi1qaCRsgeOEtERIIsgQSj4UdSuNFu+JeWUcpw/h6/yoCy3+E/W6X50cTw+PupFs4hr9dhAZaN/RHCOsMb+vd2PULSamYTEGn/Gsdr98whKujyG08d99O5iXZ9u9Jkk6wqYtIODYx7tjoD/ho+1Pv7EhP1CBIpjkggMqR22la1GEqQwYOfyaIZKVmD2GJDlHKGu1vx/vh0oX761Fn6wkMkzaB9ixwMbnQwg7uTk27b3Rb6vAtldY/MB7pLK4HVQ3bbvXJElHGNWuPmwRNsYCG9Uj+uf2FCk3Iu0RgAhCbX+uwTy0ZeUctQxuyEn9/NvLyfUtwmMboghZbxtOH0efsSHPNBbY+Mza35fX6ucHplWosCErjPu1N5wkSZqhXxCA58cQVvgyf8Dk+Nj+a8jNWNH2z/3X+v7LYPiS18gqGPPPco4aw679vDiGNBmGXY+N97/k/X06hu0sckj4kcd7DHi9duUsYZP7cCZCYr8tCY8zxNH/rTEEuL7Kxufeh9+9thZ1nl5fgZQkSSuAyg/VGUIJ95ZkEn9WvnKfLgIbc2cYCqQ/w4IcZ0Vlu+krgSgDW9v//ZPjHOO1toPARkUqfSOGOVcEI8Lbs4fTd95NgHlkZ0/O5e9Gde6vMcyhY4XsHbF5OBS3Rg13ifDFvLZE0OtXiZ4Vw/w15sP9OernyLw7Fku0+Nz6ELfXqECOrezVzmLhyrH+4AiC8+Wx3BxPSdIRRFXs5THfLv6EIfoTPubp3+O5/e2q2tZW6Ah+hJ8xOYTYzh9LPGcsNPIFudWKVX63acOO58dQ5WsR/trXItzmHL5En6/EsGhir/F7E3if0p/YIQxdE1YJ7IclfPBHwB9j8xzOWa6JGsKmYasYrstnlf/vsvr3Rcd7SJK0AhYJbKuEEMjq1GUCCVVHAt9+Yb4aIWE3MTzczx886PijZNFhbLaymfWHDNdtP6tLo1a+JUnSDqAisugQ1uml/aI/uIcY8iawLfKeW4SJfpuUMb+L+e4EMeaLsX93gZiGKinD8ov8AUGVjLmfs3Dddi5pLtjpVyZLkqQl3RyL3ZOTobX9WpHJFiZU1razyOCHMb5Io8dilH6O37xWMbDlfMd+eHsaAvF6bD3knljA0u/Vx9zHVfsMJEnSLqNawwKDZas23AqMwDLP3Coqj6woprpEReo7pX046ry9ecwb2AhFhN/3Rt1HjiHq10VdMMKwc+L3vqm0V5X2k6jVv8dEDa4fLO1zUSuP15X2gtLeV9qb7nzmYD2GYcsHR600XhLT51SeETWIjeGWaLdEHRbn/fQrksHnxmIbSZJ0RBDSro26jceiCCS5wTJtWkBpUYFjOJTq0meiBhyeu9W+c615AxsrbwmBbKXC9akgMuRMdY/tabAWdesS/gXDufneWNVLFZBq1u+jhjawVUy/AXIOW66V9oWoYYvXGVvMAl6/vVNGyuCcG0g/L8b36uO6Yxs6S5KkQ4gqVO6Vt902tip2DAsOqCD1my+PITidGxsXmnBbMUJUvwCltzZpBBsqej0CGe+5vU8q740AiifE+F58BLerYuM8P35/KnPttVpPLu3i5nGGyN5tUSuVadpCBsJiHxolSdIh9YzYfMP4ZRtbVMySQYO5cuw1x/y+rRY4bCewJVZiji1wyFuT5evnZP6+eveXybnE8y5oHvN8rnN7ab+N8UUXV8bGffoY4hwLbBxrK439ayUDmyRJ2jU5FJghiYDC/LVHRZ1fNo95h0QTr5FVsxaBh9CY8u4bvLccMuXntg9DlDxmfhvDlHeLOh+NRQHsv8ZQJgHvxNJOLe2U+rRNpg2J9u+V4VAWMvR74jkkKkmSdk2//xo/vzFqSMm7QMyySGAj0OQChx7z09rhx/Wo74cw9onJMSp8DHUmKl4ZtPL9UgHLYct2qJMAyLXOibp4oJ2HNm3RAc9tb1+W1+pvc8a1xoZKJUmSto095tjqJPHzz6IOI241NNpaJLDRbz3Gr02Yuqy0z0ddQcpt1ViAwPBphib+Zfg18ZjblzEsS9XrpKiLBHguGKL8cmnfjbo6lT40rtkuyOC1Pxmbt/W4KGqFjutfHfXabJL7hrZTDLeGkyRJ2nEM77XDeASXeVaWthYJbNw+bNa+cu0ty+jbzgvjcd5rNnG+vWY/j4z+3K4sQyJ9r2geJ1aSjlX++HxyPzeulT+nnGu3X7cukyRJOnQY7mX1KHuz9ea5NVWP69zQH5QkSdLymMt2eWln9ieirhzl3CIYVj67PyhJkqTdQ4XtWH9wBEOrhLt+aFWSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEnSavk/xzNW26jk5REAAAAASUVORK5CYII=>
# Architecture Documentation

## Overview
Industrial Knowledge Intelligence Platform architecture with documented design decisions and implementation notes.

## Stack Decisions

### LLM Provider: OpenRouter/Groq vs Anthropic
**Planned**: Claude API (Anthropic)
**Implemented**: OpenRouter with Groq API (Gemma-4 models)

**Rationale**:
- Cost efficiency: Groq provides free tier access to Gemma-4 models
- Availability: OpenRouter API more accessible for hackathon environment
- Performance: Gemma-4-26B provides sufficient quality for extraction and chat tasks
- Fallback: Multiple model options (Gemma-4-26B, Gemma-4-31B, Nemotron-3-120B)

**Trade-offs**:
- Slightly lower reasoning quality compared to Claude
- Requires internet connectivity (no local inference)
- Model availability depends on OpenRouter service

### Vector Store: ChromaDB with TF-IDF Fallback
**Planned**: ChromaDB (local mode)
**Implemented**: ChromaDB with pure-Python TF-IDF fallback

**Rationale**:
- ChromaDB requires Python ≤3.12 for current wheels
- TF-IDF fallback works on any Python version
- Ensures system works in diverse development environments
- No external dependencies for fallback (pure Python + SQLite)

**Implementation**:
- Primary: ChromaDB with sentence-transformers embeddings
- Fallback: SQLite-based TF-IDF with cosine similarity
- Automatic selection based on import success
- Both paths support same query interface

## Database Access Patterns

### Current State: Mixed Sync/Async
**Issue**: Inconsistent database access patterns across codebase
- `database.py`: Async SQLAlchemy with aiosqlite
- Most routers: Sync SQLAlchemy via `SyncSession`
- Agents: Sync access via `fact_builder.SyncSession`

### Standardization Plan
**Decision**: Standardize on synchronous access for consistency

**Rationale**:
- Simpler error handling in FastAPI routes
- Easier debugging and testing
- Sufficient performance for current workload
- Agents and routers already use sync patterns
- Async complexity not justified for current scale

**Migration Path**:
1. Keep `database.py` for async compatibility if needed in future
2. Use `SyncSession` from `fact_builder` consistently
3. Document sync pattern as standard for new code
4. Consider async only if performance becomes bottleneck

## Document Processing Pipeline

### Heterogeneous Ingestion
**Formats Supported**:
- Plain text: .txt, .md, .log
- PDF: .pdf (text layer + OCR fallback)
- Spreadsheets: .xlsx, .xls, .csv
- Email: .eml (headers + body)
- Images/Scans: .png, .jpg, .jpeg (OCR)
- P&ID: .pid, .p&id (tag extraction)

**Pipeline Stages**:
1. Format detection (`doc_formats.py`)
2. Text extraction (format-specific)
3. Metadata extraction (`parser.py`)
4. Entity extraction (`entity_extractor.py`)
5. Entity resolution (`entity_resolver.py`)
6. Persistence (`fact_builder.py`)
7. Graph construction (`graph_builder.py`)
8. Vector indexing (`vector_store.py`)

### Entity Extraction Accuracy
**Current**: Single-pass extraction with Groq API
**Evaluation Needed**: Benchmark accuracy across document types

## Compliance/Regulatory Mapping

### Implementation Status
**Defined**: `data/compliance_rules.json` with 6 regulations
**Implemented**: Basic pattern matching in `compliance_agent.py`
**Gap**: Full permit fact integration

### Regulations Covered
1. **Factory Act 1948 — Section 41B**: Hazardous process monitoring
2. **OISD-118**: Styrene storage temperature control
3. **PESO-8.3**: Pressure vessel inspection
4. **Environmental Clearance**: Valid permit requirements
5. **ISO 45001-8.1.2**: Near-miss escalation
6. **BIS Quality Standards**: Raw material traceability

### Permit Fact Integration
**Current**: Compliance agent checks for forbidden fact types
**Needed**: Direct permit status validation against permit documents

**Implementation Plan**:
- Extract permit expiration dates from permit documents
- Flag expired permits in compliance checks
- Link permit facts to specific regulatory requirements
- Add permit status to asset compliance summary

## Performance Metrics

### Search Performance
**Baseline**: Manual keyword search (estimated 7.5x slower)
**Measured**: Hybrid RAG with vector + SQL + graph expansion
**Target**: <100ms average query latency

### Pattern Detection
**Baseline**: Random matching (~20% precision)
**Measured**: Precision/recall/F1 against known patterns
**Target**: >70% precision, >60% recall

### Agent Workflows
**Baseline**: Manual analysis (RCA ~5s, Compliance ~3s, Maintenance ~4s)
**Measured**: LLM-powered agent execution
**Target**: <3s average agent response time

## API Architecture

### Router Organization
- `/timeline` - Time Machine queries
- `/patterns` - Pattern Breaker analysis
- `/graph` - Graph Explorer data
- `/chat` - Conversational RAG interface
- `/agents` - Agentic workflows (RCA, Compliance, Maintenance)
- `/ingest` - Document upload and processing
- `/validation` - Document quality validation
- `/metrics` - Performance metrics
- `/mobile` - Field technician endpoints
- `/benchmark` - Benchmark execution

### Mobile Optimization
**Design Principles**:
- Minimal response payloads
- Critical data prioritization
- Offline sync capability
- Quick asset lookup by QR/tag
- Simplified incident reporting

## Evaluation Framework

### Benchmark Suite
**Components**:
- Search performance benchmarks
- Pattern detection evaluation
- Agent workflow benchmarks
- System capacity metrics
- Chat answer quality (planned)
- Entity extraction accuracy (planned)

### Quality Metrics
**Needed**:
- Chat answer relevance scoring
- Entity extraction precision/recall by document type
- End-to-end fact accuracy validation
- User satisfaction metrics

## Deployment Considerations

### Dependencies
**Core**: Python 3.11+, FastAPI, SQLAlchemy
**Ingestion**: pypdf, openpyxl, Pillow, pytesseract, pdf2image
**Vector**: chromadb (optional), sentence-transformers (optional)
**LLM**: Groq API key via OpenRouter

### Environment Variables
```
GROQ_API_KEY - Required for LLM operations
DATABASE_URL - SQLite path (default: sqlite:///./industrial_ki.db)
CHROMA_PERSIST_DIR - ChromaDB storage (default: ./chroma_db)
UPLOAD_DIR - Document upload directory (default: ./uploads)
```

## Current Architectural Limitations

### Single-Machine Architecture
**Constraint**: Entire system designed for single-machine deployment
- SQLite database (file-based, no network access)
- Local file storage for documents and uploads
- No multi-user concurrency controls
- No multi-plant/facility isolation
- Single FastAPI instance

**Impact**:
- Not suitable for distributed deployments
- No built-in horizontal scaling
- Limited to single geographic location
- No built-in backup/replication

### Batch Processing Only
**Constraint**: LLM extraction is batch + cached, not streaming
- Entity extraction runs in batch mode
- Results cached in `.extraction_cache.json`
- No real-time streaming extraction
- No queue-based processing for large document batches

**Impact**:
- Not suitable for high-frequency document ingestion
- No real-time processing of incoming documents
- Cache invalidation not automated
- No priority-based processing

### No Incremental Ingestion
**Constraint**: No automatic updates as new records arrive
- Manual re-ingestion required for new documents
- No change detection on existing documents
- No automatic re-indexing on updates
- No event-driven processing

**Impact**:
- Manual intervention required for data freshness
- Not suitable for continuously-updated document streams
- No real-time knowledge graph updates
- Higher operational overhead

### Graph Visualization Limits
**Constraint**: Graph caps at 60 nodes for UX reasons
- Frontend graph explorer limited to 60 nodes
- Reasonable for demo/prototype UX
- Limits enterprise-scale exploration
- No pagination or lazy loading for large graphs

**Impact**:
- Cannot visualize large knowledge graphs
- Limited exploration capability for complex facilities
- Not suitable for enterprise-scale asset networks
- UX optimization limits analytical capability

## Graph Scaling Considerations

### Current Graph Implementation
**Technology**: NetworkX (in-memory graph library)
**Scale**: ~60 nodes for UX, ~1000 nodes maximum practical limit
**Storage**: JSON serialization to `knowledge_graph.json`
**Query**: In-memory traversal algorithms

### Scaling Challenges

#### Memory Constraints
- **NetworkX**: All nodes/edges loaded into memory
- **Large graphs**: 10K+ nodes consume significant RAM
- **Query performance**: Degrades with graph size
- **Serialization**: JSON becomes slow at scale

#### Query Limitations
- **Traversal depth**: Limited by recursion depth
- **Path finding**: Slow on large graphs
- **Subgraph extraction**: No efficient indexing
- **Real-time updates**: Full graph reload required

#### Visualization Constraints
- **Frontend rendering**: 60-node cap for performance
- **Force-directed layout**: O(n²) complexity
- **No pagination**: Cannot handle large graphs
- **No lazy loading**: All nodes loaded upfront

### Enterprise Graph Solutions

#### Neo4j (Recommended for Production)
**Benefits**:
- Native graph database with Cypher query language
- Handles millions of nodes/edges efficiently
- Built-in graph algorithms (centrality, path finding)
- Horizontal scaling with clustering
- Real-time query performance
- ACID compliance

**Migration Path**:
```python
# Current (NetworkX)
G = nx.Graph()
G.add_edge(asset_a, asset_b, weight=0.8)
path = nx.shortest_path(G, asset_a, asset_b)

# Migrated (Neo4j)
driver = GraphDatabase.driver("neo4j://localhost:7687")
with driver.session() as session:
    session.run("""
        MERGE (a:Asset {id: $asset_a})
        MERGE (b:Asset {id: $asset_b})
        MERGE (a)-[r:CONNECTED {weight: $weight}]->(b)
    """, asset_a=asset_a, asset_b=asset_b, weight=0.8)

    result = session.run("""
        MATCH path = shortestPath((a:Asset {id: $start})-[*]-(b:Asset {id: $end}))
        RETURN path
    """, start=asset_a, end=asset_b)
```

**Scaling Characteristics**:
- **Nodes**: Millions with proper hardware
- **Edges**: Billions with clustering
- **Query latency**: <100ms for typical queries
- **Updates**: Real-time with transactional guarantees

#### ArangoDB (Alternative)
**Benefits**:
- Multi-model (graph + document + key-value)
- Flexible schema (JSON documents)
- Good performance for mixed workloads
- Built-in graph traversal

**Trade-offs**:
- Less mature graph ecosystem than Neo4j
- Smaller community
- Fewer graph algorithms built-in

#### Amazon Neptune (Cloud-Native)
**Benefits**:
- Fully managed graph database
- Supports both Gremlin and SPARQL
- Auto-scaling capabilities
- High availability with multi-AZ

**Trade-offs**:
- Vendor lock-in to AWS
- Higher cost at scale
- Less control over configuration

### Graph Visualization Scaling

#### Subgraph Extraction
Instead of loading entire graph, extract relevant subgraphs:

```python
def get_subgraph(center_node, depth=2, max_nodes=100):
    """Extract subgraph around center node."""
    with driver.session() as session:
        result = session.run("""
            MATCH path = (center:Asset {id: $center})-[*1..{depth}]-(connected)
            WITH nodes(path) as nodes
            UNWIND nodes as node
            RETURN DISTINCT node
            LIMIT $max_nodes
        """, center=center_node, depth=depth, max_nodes=max_nodes)
        return [record for record in result]
```

#### Pagination for Large Graphs
Implement cursor-based pagination for graph exploration:

```python
def paginate_graph(cursor=None, page_size=50):
    """Paginate graph traversal."""
    with driver.session() as session:
        if cursor:
            query = """
                MATCH (a:Asset)
                WHERE id(a) > $cursor
                RETURN a
                ORDER BY id(a)
                LIMIT $page_size
            """
        else:
            query = """
                MATCH (a:Asset)
                RETURN a
                ORDER BY id(a)
                LIMIT $page_size
            """

        result = session.run(query, cursor=cursor, page_size=page_size)
        return [record for record in result]
```

#### Progressive Rendering
Load graph incrementally for better UX:

```javascript
// Frontend: Progressive graph loading
async function loadGraphProgressively(centerNode) {
    const batchSize = 20;
    let graph = { nodes: [], edges: [] };

    // Load center node
    graph.nodes.push(await fetchNode(centerNode));

    // Load neighbors in batches
    let neighbors = await fetchNeighbors(centerNode);
    for (let i = 0; i < neighbors.length; i += batchSize) {
        const batch = neighbors.slice(i, i + batchSize);
        const batchData = await fetchNodes(batch);
        graph.nodes.push(...batchData.nodes);
        graph.edges.push(...batchData.edges);
        updateVisualization(graph); // Update UI incrementally
    }

    return graph;
}
```

### Graph Algorithm Scaling

#### Centrality Measures
- **Current**: NetworkX in-memory (slow at scale)
- **Scaled**: Neo4j Graph Data Science library
- **Performance**: Sub-second for millions of nodes

#### Community Detection
- **Current**: NetworkX community algorithms (limited scale)
- **Scaled**: Neo4j Louvain method (distributed)
- **Performance**: Handles large graphs efficiently

#### Path Finding
- **Current**: NetworkX shortest path (memory-bound)
- **Scaled**: Neo4j bidirectional search (indexed)
- **Performance**: Optimized with graph indexes

### Migration Strategy

#### Phase 1: Dual-Write
- Continue using NetworkX for existing functionality
- Add Neo4j in parallel
- Write to both systems during transition
- Validate data consistency

#### Phase 2: Read-Through
- Read from Neo4j for new queries
- Fall back to NetworkX for compatibility
- Gradually migrate query endpoints
- Monitor performance differences

#### Phase 3: Cutover
- Switch all reads to Neo4j
- Deprecate NetworkX code paths
- Remove JSON serialization
- Update visualization for subgraph approach

#### Phase 4: Optimization
- Implement graph indexes
- Optimize frequent queries
- Add caching for subgraphs
- Implement progressive rendering

### Performance Targets

#### Small Graphs (<1K nodes)
- **Query latency**: <50ms
- **Visualization**: <100ms render time
- **Updates**: Real-time (<1s)

#### Medium Graphs (1K-10K nodes)
- **Query latency**: <100ms
- **Visualization**: <500ms render time (subgraph)
- **Updates**: Near real-time (<5s)

#### Large Graphs (10K-1M nodes)
- **Query latency**: <500ms (indexed queries)
- **Visualization**: <1s render time (subgraph)
- **Updates**: Batch processing (<1min)

### Cost Considerations

#### Neo4j Aura (Cloud)
- **Professional**: $0.45/hour (~$324/month)
- **Enterprise**: Custom pricing
- **Includes**: Managed service, backups, scaling

#### Self-Hosted Neo4j
- **Hardware**: 4-8 CPU, 16-32GB RAM
- **Cost**: $100-300/month (cloud instances)
- **Operations**: Additional maintenance overhead

#### Alternative: ArangoDB Cloud
- **Dedicated**: $0.24/hour (~$173/month)
- **Development**: Free tier available
- **Multi-model benefit**: Replace multiple databases

### SQLite Limitations
**Constraint**: SQLite file-based database
- No network access
- Limited concurrent writes
- No built-in replication
- No horizontal scaling
- Single point of failure

**Impact**:
- Not suitable for multi-user concurrent access
- No high availability
- Limited to single machine
- No built-in backup/restore automation
- Performance degradation with large datasets

### Local File Storage
**Constraint**: All data stored on local filesystem
- Documents stored in local directories
- No cloud storage integration
- No distributed file system support
- No CDN for static assets

**Impact**:
- Limited storage capacity
- No geographic distribution
- No built-in redundancy
- Manual backup required

## Scaling Considerations

### Current Scale
**Production Target**: ~300 facts, ~20 assets, 19 documents
**Demo Scale**: Suitable for single-facility prototype
**Enterprise Scale**: Not suitable without migration

### Bottlenecks
- **LLM API latency**: Dependent on external Groq/OpenRouter API
- **Vector index size**: ChromaDB local mode limited by machine memory
- **SQLite performance**: Degrades with large datasets (>100K facts)
- **Graph rendering**: NetworkX + frontend limits at large scale
- **Batch processing**: No streaming for large document volumes

### Enterprise Migration Path

See `ENTERPRISE_MIGRATION.md` for detailed migration planning.

### Scaling Path (Short-term)
- Larger vector store (Qdrant/Milvus for production)
- Caching for LLM responses
- Async database access for high concurrency
- Distributed processing for large document batches

### Scaling Path (Long-term)
- PostgreSQL/MySQL for multi-user support
- Cloud storage (S3/GCS) for document storage
- Message queue (RabbitMQ/Kafka) for streaming ingestion
- Distributed graph database (Neo4j/ArangoDB)
- Microservices architecture for horizontal scaling

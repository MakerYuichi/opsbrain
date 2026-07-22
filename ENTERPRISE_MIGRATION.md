# Enterprise Migration Path

## Overview
This document outlines the migration path from the current single-machine prototype to an enterprise-grade, multi-plant, cloud-ready deployment.

## Current State Assessment

### Architecture
- **Database**: SQLite (file-based, single-machine)
- **Storage**: Local filesystem
- **Processing**: Batch LLM extraction with caching
- **Deployment**: Single FastAPI instance
- **Graph**: NetworkX with 60-node UX cap
- **Scale**: ~300 facts, ~20 assets, 19 documents

### Limitations
- No multi-user concurrency
- No multi-plant/facility isolation
- No incremental/real-time ingestion
- No horizontal scaling
- Single point of failure
- Limited to single geographic location

## Target Enterprise Architecture

### Multi-Tenant Requirements
- **Multi-plant support**: Isolated data per facility
- **Multi-user access**: Concurrent user operations
- **Role-based access control**: Admin, operator, viewer roles
- **Audit logging**: Track all user actions
- **Data isolation**: Per-tenant data separation

### Cloud-Native Requirements
- **Horizontal scaling**: Auto-scaling based on load
- **High availability**: Multi-region deployment
- **Disaster recovery**: Automated backup/restore
- **Global CDN**: Fast document access worldwide
- **Managed services**: Reduce operational overhead

### Real-Time Requirements
- **Streaming ingestion**: Process documents as they arrive
- **Incremental updates**: Automatic knowledge graph updates
- **Real-time alerts**: Immediate notification of critical issues
- **Event-driven architecture**: React to data changes instantly

## Migration Phases

### Phase 1: Database Migration (SQLite → PostgreSQL)

**Objective**: Enable multi-user concurrency and better performance

**Steps**:
1. Set up PostgreSQL instance (AWS RDS or self-hosted)
2. Create database schema mirroring current SQLite structure
3. Add tenant_id column to all tables for multi-tenancy
4. Migrate existing data using pg_dump or custom migration script
5. Update database.py to use SQLAlchemy with PostgreSQL
6. Add connection pooling (PgBouncer or SQLAlchemy pool)
7. Update all database access to use tenant_id

**Code Changes**:
```python
# database.py
DATABASE_URL = "postgresql://user:pass@host:port/db"
engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=10)

# Add tenant context
def get_tenant_id():
    return get_current_tenant()  # From JWT/auth context

# Update queries
session.execute(text("SELECT * FROM facts WHERE tenant_id = :tid"), {"tid": get_tenant_id()})
```

**Benefits**:
- Multi-user concurrent access
- Better performance at scale
- ACID compliance
- Backup/restore tools

**Timeline**: 2-3 weeks

### Phase 2: Cloud Storage Migration (Local → S3/GCS)

**Objective**: Enable distributed storage and CDN access

**Steps**:
1. Set up S3 bucket or GCS bucket
2. Configure IAM roles for access
3. Update document upload to stream directly to cloud storage
4. Migrate existing documents to cloud storage
5. Update doc_formats.py to read from cloud storage URLs
6. Add CDN configuration (CloudFront or Cloud CDN)
7. Implement presigned URLs for secure access

**Code Changes**:
```python
# storage.py
import boto3

s3_client = boto3.client('s3')

def upload_document(file_bytes, key, tenant_id):
    s3_client.put_object(
        Bucket=f"opsbrain-docs-{tenant_id}",
        Key=key,
        Body=file_bytes,
        ServerSideEncryption='AES256'
    )
    return f"s3://opsbrain-docs-{tenant_id}/{key}"

def get_document_url(key, tenant_id, expires_in=3600):
    return s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': f"opsbrain-docs-{tenant_id}", 'Key': key},
        ExpiresIn=expires_in
    )
```

**Benefits**:
- Unlimited storage capacity
- Geographic distribution
- Built-in redundancy
- CDN integration

**Timeline**: 1-2 weeks

### Phase 3: Streaming Ingestion (Batch → Queue-Based)

**Objective**: Enable real-time document processing

**Steps**:
1. Set up message queue (RabbitMQ or AWS SQS/Kinesis)
2. Create document upload event producers
3. Create ingestion worker services
4. Implement streaming LLM extraction
5. Add incremental graph updates
6. Implement change detection for existing documents
7. Add priority queues for urgent documents

**Code Changes**:
```python
# ingestion_worker.py
import pika

def process_document(ch, method, properties, body):
    doc_info = json.loads(body)
    # Stream extraction
    for chunk in stream_extract_entities(doc_info):
        store_fact(chunk)
        update_graph_incremental(chunk)
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Set up consumer
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='document_ingestion')
channel.basic_consume(queue='document_ingestion', on_message_callback=process_document)
channel.start_consuming()
```

**Benefits**:
- Real-time processing
- Horizontal scaling of workers
- Priority-based processing
- Fault tolerance with message retries

**Timeline**: 3-4 weeks

### Phase 4: Vector Store Migration (ChromaDB Local → Qdrant Cloud)

**Objective**: Enable distributed vector search at scale

**Steps**:
1. Set up Qdrant Cloud instance
2. Create collections with proper sharding
3. Migrate existing embeddings using batch upsert
4. Update vector_store.py to use Qdrant client
5. Add hybrid search (keyword + vector)
6. Implement re-indexing strategies
7. Add monitoring for query performance

**Code Changes**:
```python
# vector_store.py
from qdrant_client import QdrantClient

qdrant = QdrantClient(
    url="https://your-qdrant-cluster.qdrant.io",
    api_key="your-api-key"
)

def index_facts(facts):
    qdrant.upsert(
        collection_name="industrial_facts",
        points=[
            PointStruct(
                id=f["fact_id"],
                vector=f["embedding"],
                payload={k: v for k, v in f.items() if k != "embedding"}
            )
            for f in facts
        ]
    )
```

**Benefits**:
- Horizontal scaling
- Better performance at scale
- Built-in sharding/replication
- Managed service reduces ops

**Timeline**: 2 weeks

### Phase 5: Graph Database Migration (NetworkX → Neo4j)

**Objective**: Enable enterprise-scale graph exploration

**Steps**:
1. Set up Neo4j Aura or self-hosted cluster
2. Design graph schema for asset relationships
3. Migrate existing edges to Neo4j
4. Update graph_builder.py to use Neo4j driver
5. Implement graph queries with Cypher
6. Add subgraph extraction for large graphs
7. Implement pagination for graph explorer

**Code Changes**:
```python
# graph_builder.py
from neo4j import GraphDatabase

driver = GraphDatabase.driver("neo4j://localhost:7687", auth=("user", "pass"))

def build_edge(asset_a, asset_b, relation_type, weight):
    with driver.session() as session:
        session.run("""
            MERGE (a:Asset {id: $asset_a})
            MERGE (b:Asset {id: $asset_b})
            MERGE (a)-[r:RELATION {type: $relation_type}]->(b)
            SET r.weight = $weight
        """, asset_a=asset_a, asset_b=asset_b, relation_type=relation_type, weight=weight)

def get_subgraph(center_asset, depth=2, limit=100):
    with driver.session() as session:
        result = session.run("""
            MATCH path = (a:Asset {id: $center})-[*1..{depth}]-(connected)
            RETURN path
            LIMIT $limit
        """, center=center_asset, depth=depth, limit=limit)
        return [record for record in result]
```

**Benefits**:
- Handle millions of nodes/edges
- Native graph algorithms
- Cypher query language
- Built-in clustering

**Timeline**: 3-4 weeks

### Phase 6: Microservices Architecture

**Objective**: Enable independent scaling and deployment

**Steps**:
1. Split monolith into services:
   - Ingestion Service
   - Query Service (RAG + chat)
   - Agent Service (RCA, compliance, maintenance)
   - Graph Service
   - API Gateway
2. Implement service discovery (Consul/Eureka)
3. Add inter-service communication (gRPC/REST)
4. Implement distributed tracing (Jaeger/Zipkin)
5. Add service mesh (Istio/Linkerd)
6. Containerize with Docker
7. Deploy with Kubernetes

**Architecture**:
```
API Gateway (Kong/Envoy)
├── Ingestion Service (Python)
├── Query Service (Python)
├── Agent Service (Python)
├── Graph Service (Python)
└── Auth Service (Python)

Shared Infrastructure:
├── PostgreSQL (RDS)
├── Neo4j (Aura)
├── Qdrant (Cloud)
├── RabbitMQ (MQ)
├── Redis (ElastiCache)
└── S3 (Storage)
```

**Benefits**:
- Independent scaling
- Fault isolation
- Technology diversity
- Team autonomy

**Timeline**: 6-8 weeks

### Phase 7: Multi-Tenancy & Security

**Objective**: Enable multi-plant, multi-user deployment

**Steps**:
1. Implement authentication (OAuth2/OIDC)
2. Add authorization (RBAC with roles)
3. Implement tenant context propagation
4. Add data isolation at database level
5. Implement audit logging
6. Add rate limiting per tenant
7. Implement tenant-specific configurations

**Code Changes**:
```python
# auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = decode_token(token)
    if not user:
        raise HTTPException(status_code=401)
    return user

async def get_current_tenant(user: dict = Depends(get_current_user)):
    return user["tenant_id"]

# Usage in routers
@router.get("/assets")
async def get_assets(
    tenant_id: str = Depends(get_current_tenant),
    session: Session = Depends(get_db)
):
    return session.execute(
        text("SELECT * FROM assets WHERE tenant_id = :tid"),
        {"tid": tenant_id}
    ).fetchall()
```

**Benefits**:
- Multi-plant isolation
- Secure multi-user access
- Compliance with data regulations
- Audit trail for all operations

**Timeline**: 4-5 weeks

## Deployment Architecture

### Cloud Provider Options

#### AWS
- **Database**: RDS PostgreSQL
- **Storage**: S3 + CloudFront
- **Queue**: SQS
- **Vector**: Qdrant Cloud (or self-hosted on EC2)
- **Graph**: Neo4j Aura
- **Compute**: EKS (Kubernetes) or ECS
- **Cache**: ElastiCache (Redis)

#### GCP
- **Database**: Cloud SQL
- **Storage**: GCS + Cloud CDN
- **Queue**: Pub/Sub
- **Vector**: Qdrant Cloud
- **Graph**: Neo4j Aura
- **Compute**: GKE (Kubernetes)
- **Cache**: Memorystore

#### Azure
- **Database**: Azure Database for PostgreSQL
- **Storage**: Blob Storage + Azure CDN
- **Queue**: Service Bus
- **Vector**: Qdrant Cloud
- **Graph**: Neo4j Aura
- **Compute**: AKS (Kubernetes)
- **Cache**: Azure Cache for Redis

### Infrastructure as Code
Use Terraform or CloudFormation to define infrastructure:

```hcl
# Terraform example
resource "aws_db_instance" "opsbrain_db" {
  engine         = "postgres"
  instance_class = "db.r5.large"
  allocated_storage = 100
}

resource "aws_s3_bucket" "documents" {
  bucket = "opsbrain-docs-${var.tenant_id}"
}

resource "aws_ecs_cluster" "opsbrain" {
  name = "opsbrain-cluster"
}
```

## Monitoring & Observability

### Metrics
- **Application**: Prometheus + Grafana
- **Logs**: ELK Stack or CloudWatch Logs
- **Tracing**: Jaeger or AWS X-Ray
- **Alerts**: PagerDuty or CloudWatch Alarms

### Key Metrics to Monitor
- Request latency (p50, p95, p99)
- Error rates by service
- Database connection pool usage
- Queue depth (ingestion backlog)
- Vector search latency
- Graph query performance
- LLM API latency and costs

## Cost Estimation

### Small Deployment (Single Plant)
- PostgreSQL: $50-100/month
- S3 Storage: $20-50/month
- Qdrant Cloud: $50-100/month
- Neo4j Aura: $50-100/month
- Compute (EKS): $100-200/month
- **Total**: ~$270-750/month

### Medium Deployment (Multi-Plant)
- PostgreSQL: $200-500/month
- S3 Storage: $100-300/month
- Qdrant Cloud: $200-500/month
- Neo4j Aura: $200-500/month
- Compute (EKS): $500-1000/month
- **Total**: ~$1,200-2,800/month

### Large Deployment (Enterprise)
- PostgreSQL: $500-2000/month
- S3 Storage: $300-1000/month
- Qdrant Cloud: $500-2000/month
- Neo4j Aura: $500-2000/month
- Compute (EKS): $2000-5000/month
- **Total**: ~$3,800-12,000/month

## Rollback Strategy

### Phase Rollback
Each migration phase should have a rollback plan:
- Database migration: Keep SQLite backup, use dual-write during transition
- Storage migration: Keep local copies during cloud migration
- Queue migration: Fall back to batch processing if queue fails
- Vector store: Keep ChromaDB as fallback

### Data Backup Strategy
- Daily database backups (point-in-time recovery)
- Continuous backup for S3/GCS (versioning enabled)
- Graph database snapshots (Neo4j backup)
- Configuration backups (IaC state)

## Timeline Summary

| Phase | Duration | Dependencies |
|-------|----------|-------------|
| Phase 1: Database Migration | 2-3 weeks | None |
| Phase 2: Cloud Storage | 1-2 weeks | Phase 1 |
| Phase 3: Streaming Ingestion | 3-4 weeks | Phase 1, 2 |
| Phase 4: Vector Store Migration | 2 weeks | Phase 1 |
| Phase 5: Graph Database Migration | 3-4 weeks | Phase 1 |
| Phase 6: Microservices | 6-8 weeks | Phase 1-5 |
| Phase 7: Multi-Tenancy | 4-5 weeks | Phase 6 |
| **Total** | **21-28 weeks** | **~5-7 months** |

## Recommendations

### Immediate (Next 1-2 months)
1. Start with Phase 1 (Database Migration) for immediate multi-user benefits
2. Set up basic monitoring and alerting
3. Implement backup strategy for current SQLite database

### Short-term (Next 3-6 months)
1. Complete Phase 2 (Cloud Storage) for scalability
2. Begin Phase 3 (Streaming Ingestion) for real-time capabilities
3. Plan Phase 4 (Vector Store) for performance at scale

### Long-term (6-12 months)
1. Complete Phase 5 (Graph Database) for enterprise-scale exploration
2. Plan Phase 6 (Microservices) for operational efficiency
3. Implement Phase 7 (Multi-Tenancy) for multi-plant deployment

## Risk Mitigation

### Technical Risks
- **Data migration failures**: Comprehensive testing with staging environment
- **Performance regression**: Load testing before production rollout
- **Service dependencies**: Circuit breakers and fallback mechanisms

### Operational Risks
- **Team skill gaps**: Training and hiring for new technologies
- **Cost overruns**: Regular cost reviews and optimization
- **Timeline delays**: Agile approach with incremental value delivery

### Business Risks
- **Downtime during migration**: Blue-green deployment strategy
- **Feature parity gaps**: Maintain feature parity during migration
- **User adoption**: Gradual rollout with user training

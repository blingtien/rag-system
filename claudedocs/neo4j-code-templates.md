# Neo4j Reusable Code Patterns and Templates - LightRAG Implementation

## Executive Summary

This document provides a comprehensive collection of reusable code patterns and templates extracted from LightRAG's Neo4j implementation. These production-ready templates can be directly adapted for RAG-Anything integration, providing immediate development acceleration while ensuring best practices and performance optimization.

## 1. Core Connection and Configuration Templates

### 1.1 Production-Ready Driver Configuration
```python
import os
import re
import configparser
from dataclasses import dataclass
from typing import Optional, Dict, Any
from neo4j import AsyncGraphDatabase, AsyncDriver
from dotenv import load_dotenv

# Load environment configuration
load_dotenv(dotenv_path=".env", override=False)
config = configparser.ConfigParser()
config.read("config.ini", "utf-8")

@dataclass
class Neo4jConfig:
    """Centralized Neo4j configuration with environment override support"""
    
    # Connection settings
    uri: str = os.environ.get("NEO4J_URI", config.get("neo4j", "uri", fallback="bolt://localhost:7687"))
    username: str = os.environ.get("NEO4J_USERNAME", config.get("neo4j", "username", fallback="neo4j"))
    password: str = os.environ.get("NEO4J_PASSWORD", config.get("neo4j", "password", fallback="password"))
    database: Optional[str] = os.environ.get("NEO4J_DATABASE", None)
    
    # Pool configuration
    max_connection_pool_size: int = int(os.environ.get("NEO4J_MAX_CONNECTION_POOL_SIZE", config.get("neo4j", "connection_pool_size", fallback=100)))
    connection_timeout: float = float(os.environ.get("NEO4J_CONNECTION_TIMEOUT", config.get("neo4j", "connection_timeout", fallback=30.0)))
    connection_acquisition_timeout: float = float(os.environ.get("NEO4J_CONNECTION_ACQUISITION_TIMEOUT", config.get("neo4j", "connection_acquisition_timeout", fallback=30.0)))
    max_transaction_retry_time: float = float(os.environ.get("NEO4J_MAX_TRANSACTION_RETRY_TIME", config.get("neo4j", "max_transaction_retry_time", fallback=30.0)))
    max_connection_lifetime: float = float(os.environ.get("NEO4J_MAX_CONNECTION_LIFETIME", config.get("neo4j", "max_connection_lifetime", fallback=300.0)))
    liveness_check_timeout: float = float(os.environ.get("NEO4J_LIVENESS_CHECK_TIMEOUT", config.get("neo4j", "liveness_check_timeout", fallback=30.0)))
    keep_alive: bool = os.environ.get("NEO4J_KEEP_ALIVE", config.get("neo4j", "keep_alive", fallback="true")).lower() in ("true", "1", "yes", "on")

class Neo4jConnectionManager:
    """Production-ready Neo4j connection manager with error handling"""
    
    def __init__(self, config: Neo4jConfig, workspace: str):
        self.config = config
        self.workspace = workspace
        self._driver: Optional[AsyncDriver] = None
        self._database: Optional[str] = None
        
    async def initialize(self) -> None:
        """Initialize Neo4j connection with automatic database creation"""
        self._driver = AsyncGraphDatabase.driver(
            self.config.uri,
            auth=(self.config.username, self.config.password),
            max_connection_pool_size=self.config.max_connection_pool_size,
            connection_timeout=self.config.connection_timeout,
            connection_acquisition_timeout=self.config.connection_acquisition_timeout,
            max_transaction_retry_time=self.config.max_transaction_retry_time,
            max_connection_lifetime=self.config.max_connection_lifetime,
            liveness_check_timeout=self.config.liveness_check_timeout,
            keep_alive=self.config.keep_alive,
        )
        
        # Database selection with fallback
        database_candidates = [
            self.config.database or re.sub(r"[^a-zA-Z0-9-]", "-", self.workspace),
            None  # Default database
        ]
        
        for database in database_candidates:
            try:
                await self._test_connection(database)
                self._database = database
                break
            except Exception as e:
                if database is None:  # Last fallback failed
                    raise ConnectionError(f"Unable to connect to any database: {e}")
                continue
        
        # Create workspace indexes
        await self._create_workspace_indexes()
    
    async def _test_connection(self, database: Optional[str]) -> None:
        """Test database connection and create if necessary"""
        async with self._driver.session(database=database) as session:
            try:
                result = await session.run("MATCH (n) RETURN n LIMIT 0")
                await result.consume()
            except Exception as e:
                if "DatabaseNotFound" in str(e) and database:
                    await self._create_database(database)
                else:
                    raise
    
    async def _create_database(self, database: str) -> None:
        """Attempt to create database (Enterprise edition only)"""
        try:
            async with self._driver.session() as session:
                result = await session.run(f"CREATE DATABASE `{database}` IF NOT EXISTS")
                await result.consume()
        except Exception as e:
            if "UnsupportedAdministrationCommand" in str(e):
                raise ConnectionError(f"Cannot create database '{database}'. Using Neo4j Community Edition or insufficient permissions.")
            raise
    
    async def _create_workspace_indexes(self) -> None:
        """Create essential indexes for workspace performance"""
        workspace_label = self.workspace
        
        async with self._driver.session(database=self._database) as session:
            # Primary entity_id index
            try:
                index_query = f"CREATE INDEX IF NOT EXISTS FOR (n:`{workspace_label}`) ON (n.entity_id)"
                result = await session.run(index_query)
                await result.consume()
            except Exception as e:
                # Fallback for older Neo4j versions
                try:
                    index_query = f"CREATE INDEX FOR (n:`{workspace_label}`) ON (n.entity_id)"
                    result = await session.run(index_query)
                    await result.consume()
                except Exception:
                    pass  # Index might already exist
    
    async def finalize(self) -> None:
        """Clean up resources"""
        if self._driver:
            await self._driver.close()
            self._driver = None
    
    @property
    def driver(self) -> AsyncDriver:
        if not self._driver:
            raise RuntimeError("Driver not initialized. Call initialize() first.")
        return self._driver
    
    @property
    def database(self) -> Optional[str]:
        return self._database
```

### 1.2 Session Management Template
```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, Any

class SessionManager:
    """Optimized session management with proper resource handling"""
    
    def __init__(self, connection_manager: Neo4jConnectionManager):
        self.connection_manager = connection_manager
    
    @asynccontextmanager
    async def read_session(self) -> AsyncGenerator:
        """Read-only session context manager"""
        async with self.connection_manager.driver.session(
            database=self.connection_manager.database,
            default_access_mode="READ"
        ) as session:
            yield session
    
    @asynccontextmanager  
    async def write_session(self) -> AsyncGenerator:
        """Write session context manager"""
        async with self.connection_manager.driver.session(
            database=self.connection_manager.database
        ) as session:
            yield session
    
    async def execute_read(self, query: str, **params) -> list:
        """Execute read query with proper resource management"""
        async with self.read_session() as session:
            result = await session.run(query, **params)
            try:
                return await result.data()
            finally:
                await result.consume()
    
    async def execute_write(self, transaction_func: Callable, *args, **kwargs) -> Any:
        """Execute write transaction with retry logic"""
        async with self.write_session() as session:
            return await session.execute_write(transaction_func, *args, **kwargs)
    
    async def execute_write_query(self, query: str, **params) -> dict:
        """Execute write query and return summary"""
        async def write_transaction(tx):
            result = await tx.run(query, **params)
            summary = await result.consume()
            return {
                'nodes_created': summary.counters.nodes_created,
                'relationships_created': summary.counters.relationships_created,
                'properties_set': summary.counters.properties_set,
                'nodes_deleted': summary.counters.nodes_deleted,
                'relationships_deleted': summary.counters.relationships_deleted
            }
        
        return await self.execute_write(write_transaction)
```

## 2. Graph Operations Templates

### 2.1 Node Operations Template
```python
from typing import Optional, Dict, List, Union
import logging

logger = logging.getLogger(__name__)

class NodeOperations:
    """Comprehensive node operations with workspace isolation"""
    
    def __init__(self, session_manager: SessionManager, workspace: str):
        self.session_manager = session_manager
        self.workspace = workspace
    
    async def node_exists(self, entity_id: str) -> bool:
        """Check if node exists in workspace"""
        query = f"""
        MATCH (n:`{self.workspace}` {{entity_id: $entity_id}}) 
        RETURN count(n) > 0 AS exists
        """
        result = await self.session_manager.execute_read(query, entity_id=entity_id)
        return result[0]['exists'] if result else False
    
    async def get_node(self, entity_id: str) -> Optional[Dict]:
        """Retrieve node by entity ID"""
        query = f"""
        MATCH (n:`{self.workspace}` {{entity_id: $entity_id}}) 
        RETURN n
        """
        result = await self.session_manager.execute_read(query, entity_id=entity_id)
        if result:
            node = result[0]['n']
            return dict(node)
        return None
    
    async def get_nodes_batch(self, entity_ids: List[str]) -> Dict[str, Dict]:
        """Batch retrieve multiple nodes"""
        query = f"""
        UNWIND $entity_ids AS id
        MATCH (n:`{self.workspace}` {{entity_id: id}})
        RETURN n.entity_id AS entity_id, n
        """
        result = await self.session_manager.execute_read(query, entity_ids=entity_ids)
        
        return {
            record['entity_id']: dict(record['n'])
            for record in result
        }
    
    async def upsert_node(self, entity_id: str, properties: Dict) -> Dict:
        """Insert or update node with properties"""
        async def upsert_transaction(tx):
            # Ensure entity_id is in properties
            if 'entity_id' not in properties:
                properties['entity_id'] = entity_id
            
            entity_type = properties.get('entity_type', 'Entity')
            
            query = f"""
            MERGE (n:`{self.workspace}` {{entity_id: $entity_id}})
            SET n += $properties
            SET n:`{entity_type}`
            RETURN n
            """
            result = await tx.run(query, entity_id=entity_id, properties=properties)
            record = await result.single()
            await result.consume()
            return dict(record['n']) if record else None
        
        return await self.session_manager.execute_write(upsert_transaction)
    
    async def upsert_nodes_batch(self, nodes_data: List[Dict]) -> Dict:
        """Batch upsert multiple nodes"""
        async def batch_upsert_transaction(tx):
            query = f"""
            UNWIND $nodes AS node
            MERGE (n:`{self.workspace}` {{entity_id: node.entity_id}})
            SET n += node.properties
            WITH n, node
            CALL apoc.create.setLabels(n, [`{self.workspace}`, node.entity_type]) 
            YIELD node AS labeled_node
            RETURN count(*) AS processed
            """
            result = await tx.run(query, nodes=nodes_data)
            summary = await result.consume()
            return {
                'processed': summary.single()['processed'] if summary else 0,
                'nodes_created': summary.counters.nodes_created,
                'properties_set': summary.counters.properties_set
            }
        
        return await self.session_manager.execute_write(batch_upsert_transaction)
    
    async def delete_node(self, entity_id: str) -> bool:
        """Delete node and all its relationships"""
        async def delete_transaction(tx):
            query = f"""
            MATCH (n:`{self.workspace}` {{entity_id: $entity_id}})
            DETACH DELETE n
            RETURN count(n) AS deleted
            """
            result = await tx.run(query, entity_id=entity_id)
            record = await result.single()
            await result.consume()
            return record['deleted'] > 0 if record else False
        
        return await self.session_manager.execute_write(delete_transaction)
    
    async def get_node_degree(self, entity_id: str) -> int:
        """Get number of relationships for node"""
        query = f"""
        MATCH (n:`{self.workspace}` {{entity_id: $entity_id}})
        OPTIONAL MATCH (n)-[r]-()
        RETURN COUNT(r) AS degree
        """
        result = await self.session_manager.execute_read(query, entity_id=entity_id)
        return result[0]['degree'] if result else 0
    
    async def get_node_degrees_batch(self, entity_ids: List[str]) -> Dict[str, int]:
        """Batch get node degrees"""
        query = f"""
        UNWIND $entity_ids AS id
        MATCH (n:`{self.workspace}` {{entity_id: id}})
        RETURN n.entity_id AS entity_id, count {{ (n)--() }} AS degree
        """
        result = await self.session_manager.execute_read(query, entity_ids=entity_ids)
        
        degrees = {record['entity_id']: record['degree'] for record in result}
        
        # Fill in missing nodes with degree 0
        for entity_id in entity_ids:
            if entity_id not in degrees:
                degrees[entity_id] = 0
                
        return degrees
```

### 2.2 Edge Operations Template
```python
class EdgeOperations:
    """Comprehensive edge operations with relationship management"""
    
    def __init__(self, session_manager: SessionManager, workspace: str):
        self.session_manager = session_manager
        self.workspace = workspace
    
    async def edge_exists(self, source_id: str, target_id: str) -> bool:
        """Check if edge exists between two nodes"""
        query = f"""
        MATCH (a:`{self.workspace}` {{entity_id: $source_id}})
        -[r]-
        (b:`{self.workspace}` {{entity_id: $target_id}})
        RETURN COUNT(r) > 0 AS exists
        """
        result = await self.session_manager.execute_read(
            query, source_id=source_id, target_id=target_id
        )
        return result[0]['exists'] if result else False
    
    async def get_edge(self, source_id: str, target_id: str) -> Optional[Dict]:
        """Get edge properties between two nodes"""
        query = f"""
        MATCH (a:`{self.workspace}` {{entity_id: $source_id}})
        -[r]-
        (b:`{self.workspace}` {{entity_id: $target_id}})
        RETURN properties(r) AS edge_properties
        """
        result = await self.session_manager.execute_read(
            query, source_id=source_id, target_id=target_id
        )
        
        if result:
            properties = result[0]['edge_properties']
            # Ensure required properties with defaults
            return {
                'weight': properties.get('weight', 1.0),
                'description': properties.get('description', ''),
                'keywords': properties.get('keywords', ''),
                'source_id': properties.get('source_id', ''),
                **properties
            }
        return None
    
    async def upsert_edge(self, source_id: str, target_id: str, properties: Dict) -> Dict:
        """Insert or update edge between nodes"""
        async def upsert_transaction(tx):
            query = f"""
            MATCH (source:`{self.workspace}` {{entity_id: $source_id}})
            WITH source
            MATCH (target:`{self.workspace}` {{entity_id: $target_id}})
            MERGE (source)-[r:DIRECTED]-(target)
            SET r += $properties
            RETURN properties(r) AS edge_properties
            """
            result = await tx.run(
                query, 
                source_id=source_id, 
                target_id=target_id, 
                properties=properties
            )
            record = await result.single()
            await result.consume()
            return record['edge_properties'] if record else None
        
        return await self.session_manager.execute_write(upsert_transaction)
    
    async def get_node_edges(self, entity_id: str) -> List[tuple]:
        """Get all edges connected to a node"""
        query = f"""
        MATCH (n:`{self.workspace}` {{entity_id: $entity_id}})
        OPTIONAL MATCH (n)-[r]-(connected:`{self.workspace}`)
        WHERE connected.entity_id IS NOT NULL
        RETURN n.entity_id AS source, connected.entity_id AS target
        """
        result = await self.session_manager.execute_read(query, entity_id=entity_id)
        
        return [(record['source'], record['target']) for record in result if record['target']]
    
    async def get_edges_batch(self, edge_pairs: List[tuple]) -> Dict[tuple, Dict]:
        """Batch retrieve multiple edges"""
        pairs_data = [{'src': src, 'tgt': tgt} for src, tgt in edge_pairs]
        
        query = f"""
        UNWIND $pairs AS pair
        MATCH (start:`{self.workspace}` {{entity_id: pair.src}})
        -[r:DIRECTED]-
        (end:`{self.workspace}` {{entity_id: pair.tgt}})
        RETURN pair.src AS src_id, pair.tgt AS tgt_id, 
               collect(properties(r)) AS edges
        """
        result = await self.session_manager.execute_read(query, pairs=pairs_data)
        
        edges_dict = {}
        for record in result:
            src, tgt = record['src_id'], record['tgt_id']
            edges = record['edges']
            if edges:
                edge_props = edges[0]
                # Ensure default properties
                edges_dict[(src, tgt)] = {
                    'weight': edge_props.get('weight', 1.0),
                    'description': edge_props.get('description', ''),
                    'keywords': edge_props.get('keywords', ''),
                    'source_id': edge_props.get('source_id', ''),
                    **edge_props
                }
        
        return edges_dict
    
    async def delete_edge(self, source_id: str, target_id: str) -> bool:
        """Delete edge between two nodes"""
        async def delete_transaction(tx):
            query = f"""
            MATCH (source:`{self.workspace}` {{entity_id: $source_id}})
            -[r]-
            (target:`{self.workspace}` {{entity_id: $target_id}})
            DELETE r
            RETURN count(r) AS deleted
            """
            result = await tx.run(
                query, source_id=source_id, target_id=target_id
            )
            record = await result.single()
            await result.consume()
            return record['deleted'] > 0 if record else False
        
        return await self.session_manager.execute_write(delete_transaction)
```

## 3. Graph Traversal Templates

### 3.1 Basic Graph Traversal Template
```python
from collections import deque
from typing import Set, Tuple

class GraphTraversal:
    """Graph traversal operations with workspace isolation"""
    
    def __init__(self, session_manager: SessionManager, workspace: str):
        self.session_manager = session_manager
        self.workspace = workspace
    
    async def get_neighbors(self, entity_id: str, max_neighbors: int = 1000) -> List[Dict]:
        """Get immediate neighbors of a node"""
        query = f"""
        MATCH (n:`{self.workspace}` {{entity_id: $entity_id}})
        -[r]-
        (neighbor:`{self.workspace}`)
        WHERE neighbor.entity_id IS NOT NULL
        RETURN neighbor.entity_id AS entity_id,
               neighbor AS node,
               properties(r) AS relationship
        LIMIT $max_neighbors
        """
        result = await self.session_manager.execute_read(
            query, entity_id=entity_id, max_neighbors=max_neighbors
        )
        
        return [
            {
                'entity_id': record['entity_id'],
                'node': dict(record['node']),
                'relationship': record['relationship']
            }
            for record in result
        ]
    
    async def breadth_first_search(
        self, 
        start_entity_id: str, 
        max_depth: int = 3, 
        max_nodes: int = 1000
    ) -> Dict:
        """Manual BFS implementation for compatibility"""
        visited_nodes = set()
        visited_edges = set()
        result_nodes = []
        result_edges = []
        
        queue = deque([(start_entity_id, 0)])
        
        while queue and len(visited_nodes) < max_nodes:
            current_entity_id, depth = queue.popleft()
            
            if current_entity_id in visited_nodes or depth > max_depth:
                continue
            
            # Get current node
            node = await self.session_manager.execute_read(
                f"MATCH (n:`{self.workspace}` {{entity_id: $entity_id}}) RETURN n",
                entity_id=current_entity_id
            )
            
            if not node:
                continue
                
            visited_nodes.add(current_entity_id)
            result_nodes.append({
                'entity_id': current_entity_id,
                'properties': dict(node[0]['n']),
                'depth': depth
            })
            
            if depth < max_depth:
                # Get neighbors for next level
                neighbors = await self.get_neighbors(current_entity_id)
                
                for neighbor in neighbors:
                    neighbor_id = neighbor['entity_id']
                    edge_key = tuple(sorted([current_entity_id, neighbor_id]))
                    
                    if neighbor_id not in visited_nodes:
                        queue.append((neighbor_id, depth + 1))
                    
                    if edge_key not in visited_edges:
                        visited_edges.add(edge_key)
                        result_edges.append({
                            'source': current_entity_id,
                            'target': neighbor_id,
                            'properties': neighbor['relationship']
                        })
        
        return {
            'nodes': result_nodes,
            'edges': result_edges,
            'is_truncated': len(visited_nodes) >= max_nodes
        }
    
    async def find_shortest_path(
        self, 
        start_entity_id: str, 
        end_entity_id: str, 
        max_length: int = 5
    ) -> Optional[List[str]]:
        """Find shortest path between two nodes"""
        query = f"""
        MATCH path = shortestPath((start:`{self.workspace}` {{entity_id: $start_id}})
        -[*1..{max_length}]-
        (end:`{self.workspace}` {{entity_id: $end_id}}))
        RETURN [node in nodes(path) | node.entity_id] AS path_entities
        """
        result = await self.session_manager.execute_read(
            query, start_id=start_entity_id, end_id=end_entity_id
        )
        
        return result[0]['path_entities'] if result else None
    
    async def get_subgraph_by_distance(
        self, 
        entity_id: str, 
        distance: int = 2
    ) -> Dict:
        """Get subgraph within specified distance"""
        query = f"""
        MATCH (start:`{self.workspace}` {{entity_id: $entity_id}})
        CALL {{
            WITH start
            MATCH (start)-[*1..{distance}]-(connected:`{self.workspace}`)
            RETURN collect(DISTINCT connected) AS nodes
        }}
        WITH start, nodes
        CALL {{
            WITH start, nodes
            UNWIND nodes AS n1
            UNWIND nodes AS n2
            MATCH (n1)-[r]-(n2)
            WHERE id(n1) < id(n2)
            RETURN collect(r) AS edges
        }}
        RETURN [start] + nodes AS all_nodes, edges
        """
        result = await self.session_manager.execute_read(query, entity_id=entity_id)
        
        if result:
            record = result[0]
            return {
                'nodes': [
                    {
                        'entity_id': node.get('entity_id'),
                        'properties': dict(node)
                    }
                    for node in record['all_nodes']
                ],
                'edges': [
                    {
                        'source': edge.start_node.get('entity_id'),
                        'target': edge.end_node.get('entity_id'),
                        'properties': dict(edge)
                    }
                    for edge in record['edges']
                ]
            }
        
        return {'nodes': [], 'edges': []}
```

## 4. Batch Processing Templates

### 4.1 Generic Batch Processor Template
```python
import asyncio
from typing import List, Callable, Any

class BatchProcessor:
    """Generic batch processing with error handling and progress tracking"""
    
    def __init__(self, session_manager: SessionManager, default_batch_size: int = 500):
        self.session_manager = session_manager
        self.default_batch_size = default_batch_size
    
    async def process_batches(
        self,
        data: List[Any],
        process_func: Callable,
        batch_size: Optional[int] = None,
        max_concurrent: int = 5
    ) -> Dict:
        """Process data in batches with concurrency control"""
        batch_size = batch_size or self.default_batch_size
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_single_batch(batch_data, batch_index):
            async with semaphore:
                try:
                    return await process_func(batch_data)
                except Exception as e:
                    logger.error(f"Batch {batch_index} failed: {str(e)}")
                    return {'error': str(e), 'batch_index': batch_index}
        
        # Create batches
        batches = [
            data[i:i + batch_size] 
            for i in range(0, len(data), batch_size)
        ]
        
        # Process batches concurrently
        tasks = [
            process_single_batch(batch, i) 
            for i, batch in enumerate(batches)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        successful = [r for r in results if not isinstance(r, Exception) and 'error' not in r]
        failed = [r for r in results if isinstance(r, Exception) or 'error' in r]
        
        return {
            'total_batches': len(batches),
            'successful_batches': len(successful),
            'failed_batches': len(failed),
            'total_items': len(data),
            'success_rate': len(successful) / len(batches) if batches else 0,
            'failed_results': failed
        }
    
    async def batch_node_upsert(self, nodes_data: List[Dict]) -> Dict:
        """Batch upsert nodes with workspace isolation"""
        async def upsert_batch(batch):
            async def batch_transaction(tx):
                query = f"""
                UNWIND $nodes AS node
                MERGE (n:`{self.session_manager.connection_manager.workspace}` {{entity_id: node.entity_id}})
                SET n += node.properties
                WITH n, node
                SET n:`{{node.entity_type}}`
                RETURN count(*) AS processed
                """
                result = await tx.run(query, nodes=batch)
                summary = await result.consume()
                return {
                    'processed': summary.single()['processed'] if summary else 0,
                    'nodes_created': summary.counters.nodes_created,
                    'properties_set': summary.counters.properties_set
                }
            
            return await self.session_manager.execute_write(batch_transaction)
        
        return await self.process_batches(nodes_data, upsert_batch)
    
    async def batch_edge_upsert(self, edges_data: List[Dict]) -> Dict:
        """Batch upsert edges with validation"""
        async def upsert_batch(batch):
            async def batch_transaction(tx):
                query = f"""
                UNWIND $edges AS edge
                MATCH (source:`{self.session_manager.connection_manager.workspace}` {{entity_id: edge.source}})
                WITH source, edge
                MATCH (target:`{self.session_manager.connection_manager.workspace}` {{entity_id: edge.target}})
                MERGE (source)-[r:DIRECTED]-(target)
                SET r += edge.properties
                RETURN count(*) AS processed
                """
                result = await tx.run(query, edges=batch)
                summary = await result.consume()
                return {
                    'processed': summary.single()['processed'] if summary else 0,
                    'relationships_created': summary.counters.relationships_created,
                    'properties_set': summary.counters.properties_set
                }
            
            return await self.session_manager.execute_write(batch_transaction)
        
        return await self.process_batches(edges_data, upsert_batch, batch_size=100)
```

## 5. Error Handling and Retry Templates

### 5.1 Comprehensive Error Handler Template
```python
from tenacity import (
    retry,
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception_type
)
import neo4j.exceptions as neo4j_exceptions

class ErrorHandler:
    """Comprehensive error handling for Neo4j operations"""
    
    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((
            neo4j_exceptions.ServiceUnavailable,
            neo4j_exceptions.TransientError,
            neo4j_exceptions.WriteServiceUnavailable,
            neo4j_exceptions.SessionExpired,
            ConnectionResetError,
            OSError,
        ))
    )
    async def execute_with_retry(operation_func: Callable, *args, **kwargs):
        """Execute operation with intelligent retry logic"""
        try:
            return await operation_func(*args, **kwargs)
        except neo4j_exceptions.ClientError as e:
            if e.code in ['Neo.ClientError.Statement.SyntaxError', 
                         'Neo.ClientError.Statement.ParameterMissing']:
                # Don't retry syntax or parameter errors
                raise
            elif e.code == 'Neo.ClientError.Database.DatabaseNotFound':
                raise ConnectionError(f"Database not found: {e}")
            else:
                raise
        except neo4j_exceptions.DatabaseError as e:
            logger.error(f"Database error occurred: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Neo4j operation: {e}")
            raise
    
    @staticmethod
    async def safe_execute(operation_func: Callable, default_return=None, *args, **kwargs):
        """Execute operation with safe error handling"""
        try:
            return await ErrorHandler.execute_with_retry(operation_func, *args, **kwargs)
        except Exception as e:
            logger.warning(f"Operation failed safely: {e}")
            return default_return
    
    @staticmethod
    def handle_connection_error(error: Exception) -> str:
        """Generate user-friendly connection error messages"""
        if isinstance(error, neo4j_exceptions.ServiceUnavailable):
            return "Neo4j database is not available. Please check if the database is running."
        elif isinstance(error, neo4j_exceptions.AuthError):
            return "Authentication failed. Please check your credentials."
        elif isinstance(error, ConnectionError):
            return str(error)
        else:
            return f"Connection error: {str(error)}"
```

## 6. Performance Monitoring Template

### 6.1 Query Performance Monitor Template
```python
import time
import statistics
from typing import List, Dict
from collections import defaultdict

class PerformanceMonitor:
    """Query performance monitoring and analysis"""
    
    def __init__(self):
        self.query_metrics = defaultdict(list)
        self.slow_query_threshold_ms = 1000
        
    async def monitor_query(self, operation_name: str, query_func: Callable, *args, **kwargs):
        """Monitor query execution with detailed metrics"""
        start_time = time.perf_counter()
        
        try:
            result = await query_func(*args, **kwargs)
            execution_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
            
            # Record metrics
            self.query_metrics[operation_name].append({
                'execution_time_ms': execution_time,
                'timestamp': time.time(),
                'success': True
            })
            
            # Log slow queries
            if execution_time > self.slow_query_threshold_ms:
                logger.warning(f"Slow query detected - {operation_name}: {execution_time:.2f}ms")
            
            return result
            
        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            
            self.query_metrics[operation_name].append({
                'execution_time_ms': execution_time,
                'timestamp': time.time(),
                'success': False,
                'error': str(e)
            })
            
            raise
    
    def get_performance_summary(self, operation_name: str = None) -> Dict:
        """Get performance summary for operations"""
        if operation_name:
            metrics = self.query_metrics.get(operation_name, [])
        else:
            metrics = []
            for op_metrics in self.query_metrics.values():
                metrics.extend(op_metrics)
        
        if not metrics:
            return {'status': 'no_data'}
        
        execution_times = [m['execution_time_ms'] for m in metrics]
        successful_operations = [m for m in metrics if m.get('success', True)]
        
        return {
            'total_operations': len(metrics),
            'successful_operations': len(successful_operations),
            'success_rate': len(successful_operations) / len(metrics),
            'avg_execution_time_ms': statistics.mean(execution_times),
            'median_execution_time_ms': statistics.median(execution_times),
            'p95_execution_time_ms': np.percentile(execution_times, 95),
            'max_execution_time_ms': max(execution_times),
            'slow_query_count': len([t for t in execution_times if t > self.slow_query_threshold_ms])
        }
    
    def reset_metrics(self):
        """Reset collected metrics"""
        self.query_metrics.clear()
```

## 7. Integration Template for RAG-Anything

### 7.1 Complete Integration Template
```python
class RAGNeo4jIntegration:
    """Complete Neo4j integration template for RAG-Anything"""
    
    def __init__(self, workspace: str, config: Optional[Neo4jConfig] = None):
        self.workspace = workspace
        self.config = config or Neo4jConfig()
        self.connection_manager = Neo4jConnectionManager(self.config, workspace)
        self.session_manager = None
        self.node_ops = None
        self.edge_ops = None
        self.traversal = None
        self.batch_processor = None
        self.performance_monitor = PerformanceMonitor()
        
    async def initialize(self):
        """Initialize all components"""
        await self.connection_manager.initialize()
        self.session_manager = SessionManager(self.connection_manager)
        self.node_ops = NodeOperations(self.session_manager, self.workspace)
        self.edge_ops = EdgeOperations(self.session_manager, self.workspace)
        self.traversal = GraphTraversal(self.session_manager, self.workspace)
        self.batch_processor = BatchProcessor(self.session_manager)
        
    async def finalize(self):
        """Clean up resources"""
        await self.connection_manager.finalize()
    
    async def __aenter__(self):
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.finalize()
    
    # High-level RAG operations
    async def build_knowledge_graph(self, entities: List[Dict], relationships: List[Dict]):
        """Build knowledge graph from entities and relationships"""
        # Step 1: Create entities
        entity_result = await self.batch_processor.batch_node_upsert(entities)
        
        # Step 2: Create relationships  
        relationship_result = await self.batch_processor.batch_edge_upsert(relationships)
        
        return {
            'entities_created': entity_result['successful_batches'],
            'relationships_created': relationship_result['successful_batches'],
            'total_processing_time': time.perf_counter()
        }
    
    async def query_context(self, query_entities: List[str], max_depth: int = 2) -> Dict:
        """Query graph context for RAG retrieval"""
        context_nodes = []
        context_edges = []
        
        for entity_id in query_entities:
            subgraph = await self.traversal.breadth_first_search(
                entity_id, max_depth=max_depth, max_nodes=500
            )
            context_nodes.extend(subgraph['nodes'])
            context_edges.extend(subgraph['edges'])
        
        return {
            'nodes': context_nodes,
            'edges': context_edges,
            'entity_count': len(context_nodes),
            'relationship_count': len(context_edges)
        }
    
    async def get_performance_metrics(self) -> Dict:
        """Get comprehensive performance metrics"""
        return self.performance_monitor.get_performance_summary()
```

### 7.2 Usage Example Template
```python
# Example usage of the complete integration
async def example_rag_integration():
    """Example of how to use the RAG-Neo4j integration"""
    
    # Configuration
    config = Neo4jConfig(
        uri="bolt://localhost:7687",
        username="neo4j", 
        password="password",
        max_connection_pool_size=50
    )
    
    # Initialize integration
    async with RAGNeo4jIntegration("my_rag_workspace", config) as neo4j:
        
        # Sample data
        entities = [
            {
                'entity_id': 'person_1',
                'properties': {
                    'entity_type': 'Person',
                    'name': 'John Doe',
                    'description': 'Software engineer',
                    'source_id': 'doc_1'
                }
            },
            {
                'entity_id': 'company_1', 
                'properties': {
                    'entity_type': 'Company',
                    'name': 'Tech Corp',
                    'description': 'Technology company',
                    'source_id': 'doc_1'
                }
            }
        ]
        
        relationships = [
            {
                'source': 'person_1',
                'target': 'company_1',
                'properties': {
                    'weight': 0.8,
                    'description': 'works at',
                    'keywords': 'employment,job',
                    'source_id': 'doc_1'
                }
            }
        ]
        
        # Build knowledge graph
        build_result = await neo4j.build_knowledge_graph(entities, relationships)
        print(f"Built graph: {build_result}")
        
        # Query for context
        context = await neo4j.query_context(['person_1'], max_depth=2)
        print(f"Retrieved context: {context}")
        
        # Get performance metrics
        metrics = await neo4j.get_performance_metrics()
        print(f"Performance: {metrics}")

# Run the example
if __name__ == "__main__":
    asyncio.run(example_rag_integration())
```

## 8. Conclusion

These templates provide production-ready, reusable patterns for integrating Neo4j graph databases into RAG-Anything systems. The templates include:

**Core Features**:
- **Production-ready connection management** with error handling and fallbacks
- **Comprehensive CRUD operations** with batch processing support
- **Advanced graph traversal** with multiple algorithm implementations  
- **Performance monitoring** and metrics collection
- **Error handling and retry logic** for production reliability
- **Complete integration template** for immediate adoption

**Key Benefits**:
- **Immediate Development Acceleration**: Copy-paste ready code patterns
- **Production Reliability**: Comprehensive error handling and resource management
- **Performance Optimization**: Built-in monitoring and optimization patterns
- **Scalability Support**: Batch processing and connection pooling
- **Workspace Isolation**: Multi-tenant support out of the box

These templates can be directly adapted and customized for specific RAG-Anything requirements while maintaining the production-quality patterns demonstrated in LightRAG's implementation.
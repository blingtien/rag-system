#!/usr/bin/env python3
"""
Database Cleanup Strategy for Corrupted DOC Content
Comprehensive cleanup and optimization tools for removing corrupted content from LightRAG
"""

import json
import re
import os
import logging
from typing import Dict, List, Set, Tuple
from pathlib import Path
import networkx as nx

logger = logging.getLogger(__name__)

class CorruptedContentCleaner:
    """Handles cleanup of corrupted DOC content from LightRAG database"""
    
    def __init__(self, rag_storage_path: str = "/home/ragsvr/projects/ragsystem/rag_storage"):
        self.storage_path = Path(rag_storage_path)
        self.corruption_patterns = [
            r'[规]{10,}',  # Repeated 规 characters
            r'[国]{10,}',  # Repeated 国 characters  
            r'[《》、、。]{10,}',  # Repeated punctuation
            r'一规规规规规规规规规',  # Mixed corruption patterns
            r'国国国国国国国国国国',  # Repeated 国
        ]
        
        # Files affected by corruption
        self.affected_files = [
            'kv_store_full_docs.json',
            'kv_store_text_chunks.json', 
            'kv_store_full_entities.json',
            'kv_store_full_relations.json',
            'kv_store_parse_cache.json',
            'kv_store_llm_response_cache.json',
            'graph_chunk_entity_relation.graphml',
            'vdb_chunks.json'
        ]
        
        self.corrupted_doc_id = "doc-6e47ad927400356d3df5f2712ea35108"
        self.stats = {
            'documents_cleaned': 0,
            'chunks_removed': 0,
            'entities_removed': 0,
            'relations_removed': 0,
            'cache_entries_cleared': 0,
            'vector_embeddings_removed': 0
        }
    
    def detect_corruption(self, text: str) -> bool:
        """Detect if text content is corrupted using regex patterns"""
        if not text or len(text.strip()) == 0:
            return False
            
        for pattern in self.corruption_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def backup_database(self) -> str:
        """Create backup of database before cleanup"""
        import shutil
        from datetime import datetime
        
        backup_dir = self.storage_path.parent / f"rag_storage_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir.mkdir(exist_ok=True)
        
        logger.info(f"Creating database backup at: {backup_dir}")
        shutil.copytree(self.storage_path, backup_dir / "rag_storage")
        
        return str(backup_dir)
    
    def clean_full_docs(self) -> int:
        """Clean corrupted documents from kv_store_full_docs.json"""
        file_path = self.storage_path / 'kv_store_full_docs.json'
        
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        removed_count = 0
        docs_to_remove = []
        
        for doc_id, doc_data in data.items():
            content = doc_data.get('content', '')
            if self.detect_corruption(content):
                docs_to_remove.append(doc_id)
                logger.info(f"Marking corrupted document for removal: {doc_id}")
                removed_count += 1
        
        # Remove corrupted documents
        for doc_id in docs_to_remove:
            del data[doc_id]
        
        # Write cleaned data back
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.stats['documents_cleaned'] = removed_count
        logger.info(f"Removed {removed_count} corrupted documents from full_docs")
        return removed_count
    
    def clean_text_chunks(self) -> int:
        """Clean corrupted chunks from kv_store_text_chunks.json"""
        file_path = self.storage_path / 'kv_store_text_chunks.json'
        
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        removed_count = 0
        chunks_to_remove = []
        
        for chunk_id, chunk_content in data.items():
            if self.detect_corruption(chunk_content):
                chunks_to_remove.append(chunk_id)
                removed_count += 1
        
        # Remove corrupted chunks
        for chunk_id in chunks_to_remove:
            del data[chunk_id]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.stats['chunks_removed'] = removed_count
        logger.info(f"Removed {removed_count} corrupted chunks")
        return removed_count
    
    def clean_entities(self) -> int:
        """Clean corrupted entities from kv_store_full_entities.json"""
        file_path = self.storage_path / 'kv_store_full_entities.json'
        
        if not file_path.exists():
            return 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        removed_count = 0
        entities_to_remove = []
        
        for entity_id, entity_data in data.items():
            # Check entity name and description for corruption
            entity_content = entity_data.get('entity_name', '') + ' ' + entity_data.get('entity_desc', '')
            if self.detect_corruption(entity_content):
                entities_to_remove.append(entity_id)
                removed_count += 1
        
        for entity_id in entities_to_remove:
            del data[entity_id]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.stats['entities_removed'] = removed_count
        logger.info(f"Removed {removed_count} corrupted entities")
        return removed_count
    
    def clean_relations(self) -> int:
        """Clean corrupted relationships from kv_store_full_relations.json"""
        file_path = self.storage_path / 'kv_store_full_relations.json'
        
        if not file_path.exists():
            return 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        removed_count = 0
        relations_to_remove = []
        
        for rel_id, rel_data in data.items():
            # Check relation description and keywords for corruption
            rel_content = (rel_data.get('relation_desc', '') + ' ' + 
                          rel_data.get('src_id', '') + ' ' + 
                          rel_data.get('tgt_id', '') + ' ' +
                          ' '.join(rel_data.get('keywords', [])))
            
            if self.detect_corruption(rel_content):
                relations_to_remove.append(rel_id)
                removed_count += 1
        
        for rel_id in relations_to_remove:
            del data[rel_id]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.stats['relations_removed'] = removed_count
        logger.info(f"Removed {removed_count} corrupted relations")
        return removed_count
    
    def clean_caches(self) -> int:
        """Clean corrupted entries from cache files"""
        cache_files = ['kv_store_parse_cache.json', 'kv_store_llm_response_cache.json']
        total_removed = 0
        
        for cache_file in cache_files:
            file_path = self.storage_path / cache_file
            if not file_path.exists():
                continue
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            removed_count = 0
            keys_to_remove = []
            
            for key, value in data.items():
                # Convert value to string for corruption check
                value_str = str(value) if not isinstance(value, str) else value
                if self.detect_corruption(value_str):
                    keys_to_remove.append(key)
                    removed_count += 1
            
            for key in keys_to_remove:
                del data[key]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            total_removed += removed_count
            logger.info(f"Removed {removed_count} corrupted entries from {cache_file}")
        
        self.stats['cache_entries_cleared'] = total_removed
        return total_removed
    
    def clean_vector_database(self) -> int:
        """Clean corrupted vectors from vdb_chunks.json"""
        file_path = self.storage_path / 'vdb_chunks.json'
        
        if not file_path.exists():
            return 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        removed_count = 0
        
        # The vector DB typically stores embeddings with metadata
        # We need to check the text content associated with vectors
        if isinstance(data, list):
            clean_data = []
            for item in data:
                if isinstance(item, dict):
                    text_content = item.get('text', '') or item.get('content', '') or str(item.get('metadata', {}))
                    if not self.detect_corruption(text_content):
                        clean_data.append(item)
                    else:
                        removed_count += 1
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(clean_data, f, ensure_ascii=False, indent=2)
        
        self.stats['vector_embeddings_removed'] = removed_count
        logger.info(f"Removed {removed_count} corrupted vector embeddings")
        return removed_count
    
    def clean_graph_file(self) -> int:
        """Clean corrupted nodes/edges from GraphML file"""
        file_path = self.storage_path / 'graph_chunk_entity_relation.graphml'
        
        if not file_path.exists():
            return 0
        
        try:
            # Read GraphML file
            graph = nx.read_graphml(file_path)
            
            # Count nodes/edges before cleaning
            original_nodes = len(graph.nodes())
            original_edges = len(graph.edges())
            
            # Remove corrupted nodes
            corrupted_nodes = []
            for node_id, node_data in graph.nodes(data=True):
                node_content = ' '.join([str(v) for v in node_data.values()])
                if self.detect_corruption(node_content):
                    corrupted_nodes.append(node_id)
            
            graph.remove_nodes_from(corrupted_nodes)
            
            # Remove corrupted edges
            corrupted_edges = []
            for source, target, edge_data in graph.edges(data=True):
                edge_content = ' '.join([str(v) for v in edge_data.values()])
                if self.detect_corruption(edge_content):
                    corrupted_edges.append((source, target))
            
            graph.remove_edges_from(corrupted_edges)
            
            # Write cleaned graph back
            nx.write_graphml(graph, file_path)
            
            removed_count = (original_nodes + original_edges) - (len(graph.nodes()) + len(graph.edges()))
            logger.info(f"Removed {removed_count} corrupted graph elements")
            return removed_count
            
        except Exception as e:
            logger.error(f"Error cleaning graph file: {e}")
            return 0
    
    def run_full_cleanup(self) -> Dict:
        """Execute complete database cleanup process"""
        logger.info("Starting comprehensive database cleanup...")
        
        # Create backup first
        backup_path = self.backup_database()
        logger.info(f"Database backup created: {backup_path}")
        
        try:
            # Execute all cleanup operations
            self.clean_full_docs()
            self.clean_text_chunks()
            self.clean_entities()
            self.clean_relations()
            self.clean_caches()
            self.clean_vector_database()
            self.clean_graph_file()
            
            # Calculate total impact
            total_removed = sum([
                self.stats['documents_cleaned'],
                self.stats['chunks_removed'], 
                self.stats['entities_removed'],
                self.stats['relations_removed'],
                self.stats['cache_entries_cleared'],
                self.stats['vector_embeddings_removed']
            ])
            
            cleanup_report = {
                'status': 'success',
                'backup_location': backup_path,
                'cleanup_stats': self.stats,
                'total_items_removed': total_removed,
                'corrupted_doc_id': self.corrupted_doc_id
            }
            
            logger.info("Database cleanup completed successfully!")
            logger.info(f"Total items removed: {total_removed}")
            
            return cleanup_report
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'backup_location': backup_path
            }


class DatabaseOptimizer:
    """Optimizes database performance after cleanup"""
    
    def __init__(self, rag_storage_path: str = "/home/ragsvr/projects/ragsystem/rag_storage"):
        self.storage_path = Path(rag_storage_path)
    
    def rebuild_indexes(self):
        """Rebuild database indexes after cleanup"""
        logger.info("Rebuilding database indexes...")
        
        # For LightRAG, this typically means:
        # 1. Recompute vector embeddings for remaining content
        # 2. Rebuild knowledge graph connections
        # 3. Update search indexes
        
        # This would require integration with LightRAG's internal rebuild methods
        # For now, we'll log the recommendation
        logger.info("Index rebuild recommended - restart RAG service to trigger automatic rebuild")
    
    def optimize_storage(self):
        """Optimize storage after cleanup"""
        logger.info("Optimizing storage files...")
        
        # Compact JSON files by removing unnecessary whitespace
        json_files = ['kv_store_full_docs.json', 'kv_store_text_chunks.json', 
                     'kv_store_full_entities.json', 'kv_store_full_relations.json']
        
        for json_file in json_files:
            file_path = self.storage_path / json_file
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Write back with compact format
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        
        logger.info("Storage optimization complete")


def main():
    """Main cleanup execution"""
    cleaner = CorruptedContentCleaner()
    
    # Run cleanup
    report = cleaner.run_full_cleanup()
    
    if report['status'] == 'success':
        # Run optimization
        optimizer = DatabaseOptimizer()
        optimizer.optimize_storage()
        optimizer.rebuild_indexes()
        
        print("\n=== CLEANUP REPORT ===")
        print(f"Status: {report['status']}")
        print(f"Backup Location: {report['backup_location']}")
        print(f"Total Items Removed: {report['total_items_removed']}")
        print("\nDetailed Stats:")
        for stat, count in report['cleanup_stats'].items():
            print(f"  {stat}: {count}")
    else:
        print(f"Cleanup failed: {report['error']}")
        print(f"Backup available at: {report['backup_location']}")


if __name__ == "__main__":
    main()
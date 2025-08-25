#!/usr/bin/env python3
"""
Schema Enhancement Strategy for Content Quality Tracking
Extends LightRAG storage schema with quality metrics and corruption detection
"""

import json
import hashlib
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class ContentQualityProfile:
    """Comprehensive content quality profile"""
    doc_id: str
    file_name: str
    file_path: str
    
    # Quality Metrics
    corruption_score: float  # 0.0 = clean, 1.0 = completely corrupted
    readability_score: float  # 0.0 = unreadable, 1.0 = highly readable
    information_density: float  # 0.0 = no info, 1.0 = high info density
    confidence_score: float  # Overall quality confidence
    
    # Processing Metadata
    parser_used: str  # "mineru", "docling", "libreoffice"
    parsing_method: str  # "auto", "ocr", "text"
    processing_time: float
    content_length: int
    chunk_count: int
    
    # Quality Flags
    has_corruption: bool
    corruption_patterns: List[str]
    needs_reprocessing: bool
    is_usable: bool
    
    # Timestamps
    created_at: str
    last_assessed: str
    quality_version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContentQualityProfile':
        """Create from dictionary"""
        return cls(**data)


class ContentQualityTracker:
    """Tracks and manages content quality across the RAG system"""
    
    def __init__(self, storage_path: str = "/home/ragsvr/projects/ragsystem/rag_storage"):
        self.storage_path = Path(storage_path)
        self.quality_db_path = self.storage_path / "content_quality_profiles.json"
        self.quality_index_path = self.storage_path / "quality_index.json"
        self.quality_stats_path = self.storage_path / "quality_statistics.json"
        
        # Initialize quality database
        self._init_quality_database()
    
    def _init_quality_database(self):
        """Initialize quality tracking database files"""
        # Quality profiles database
        if not self.quality_db_path.exists():
            self._save_quality_database({})
            logger.info("Initialized content quality profiles database")
        
        # Quality index for fast lookups
        if not self.quality_index_path.exists():
            self._save_quality_index({
                'by_corruption_score': {},
                'by_confidence_score': {},
                'by_parser': {},
                'corrupted_docs': [],
                'high_quality_docs': [],
                'needs_reprocessing': []
            })
            logger.info("Initialized quality index")
        
        # Quality statistics
        if not self.quality_stats_path.exists():
            self._save_quality_stats({
                'total_documents': 0,
                'corrupted_count': 0,
                'high_quality_count': 0,
                'avg_corruption_score': 0.0,
                'avg_confidence_score': 0.0,
                'parser_performance': {},
                'last_updated': datetime.now(timezone.utc).isoformat()
            })
            logger.info("Initialized quality statistics")
    
    def _save_quality_database(self, data: Dict[str, Any]):
        """Save quality database to file"""
        with open(self.quality_db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_quality_database(self) -> Dict[str, Any]:
        """Load quality database from file"""
        with open(self.quality_db_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_quality_index(self, data: Dict[str, Any]):
        """Save quality index to file"""
        with open(self.quality_index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_quality_index(self) -> Dict[str, Any]:
        """Load quality index from file"""
        with open(self.quality_index_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_quality_stats(self, data: Dict[str, Any]):
        """Save quality statistics to file"""
        with open(self.quality_stats_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_quality_stats(self) -> Dict[str, Any]:
        """Load quality statistics from file"""
        with open(self.quality_stats_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def create_quality_profile(self, doc_id: str, file_name: str, file_path: str,
                             corruption_score: float, readability_score: float,
                             information_density: float, confidence_score: float,
                             parser_used: str, parsing_method: str,
                             processing_time: float, content_length: int,
                             chunk_count: int, corruption_patterns: List[str]) -> ContentQualityProfile:
        """Create a quality profile for a document"""
        
        profile = ContentQualityProfile(
            doc_id=doc_id,
            file_name=file_name,
            file_path=file_path,
            corruption_score=corruption_score,
            readability_score=readability_score,
            information_density=information_density,
            confidence_score=confidence_score,
            parser_used=parser_used,
            parsing_method=parsing_method,
            processing_time=processing_time,
            content_length=content_length,
            chunk_count=chunk_count,
            has_corruption=corruption_score > 0.3,
            corruption_patterns=corruption_patterns,
            needs_reprocessing=corruption_score > 0.5 or confidence_score < 0.2,
            is_usable=confidence_score >= 0.3 and corruption_score < 0.7,
            created_at=datetime.now(timezone.utc).isoformat(),
            last_assessed=datetime.now(timezone.utc).isoformat()
        )
        
        return profile
    
    def save_quality_profile(self, profile: ContentQualityProfile):
        """Save quality profile to database and update indexes"""
        # Load current database
        quality_db = self._load_quality_database()
        quality_index = self._load_quality_index()
        
        # Save profile
        quality_db[profile.doc_id] = profile.to_dict()
        
        # Update indexes
        self._update_quality_index(quality_index, profile)
        
        # Save back to files
        self._save_quality_database(quality_db)
        self._save_quality_index(quality_index)
        
        # Update statistics
        self._update_quality_statistics()
        
        logger.info(f"Saved quality profile for document: {profile.doc_id}")
    
    def _update_quality_index(self, index: Dict[str, Any], profile: ContentQualityProfile):
        """Update quality indexes with new profile"""
        doc_id = profile.doc_id
        
        # Update corruption score index
        corruption_bucket = self._get_score_bucket(profile.corruption_score)
        if corruption_bucket not in index['by_corruption_score']:
            index['by_corruption_score'][corruption_bucket] = []
        if doc_id not in index['by_corruption_score'][corruption_bucket]:
            index['by_corruption_score'][corruption_bucket].append(doc_id)
        
        # Update confidence score index
        confidence_bucket = self._get_score_bucket(profile.confidence_score)
        if confidence_bucket not in index['by_confidence_score']:
            index['by_confidence_score'][confidence_bucket] = []
        if doc_id not in index['by_confidence_score'][confidence_bucket]:
            index['by_confidence_score'][confidence_bucket].append(doc_id)
        
        # Update parser index
        if profile.parser_used not in index['by_parser']:
            index['by_parser'][profile.parser_used] = []
        if doc_id not in index['by_parser'][profile.parser_used]:
            index['by_parser'][profile.parser_used].append(doc_id)
        
        # Update status lists
        if profile.has_corruption and doc_id not in index['corrupted_docs']:
            index['corrupted_docs'].append(doc_id)
        
        if profile.confidence_score >= 0.8 and doc_id not in index['high_quality_docs']:
            index['high_quality_docs'].append(doc_id)
        
        if profile.needs_reprocessing and doc_id not in index['needs_reprocessing']:
            index['needs_reprocessing'].append(doc_id)
    
    def _get_score_bucket(self, score: float) -> str:
        """Get score bucket for indexing (0.0-0.2, 0.2-0.4, etc.)"""
        bucket = int(score * 5) * 0.2
        return f"{bucket:.1f}-{bucket + 0.2:.1f}"
    
    def _update_quality_statistics(self):
        """Update quality statistics"""
        quality_db = self._load_quality_database()
        
        if not quality_db:
            return
        
        total_docs = len(quality_db)
        corrupted_count = sum(1 for p in quality_db.values() if p['has_corruption'])
        high_quality_count = sum(1 for p in quality_db.values() if p['confidence_score'] >= 0.8)
        
        avg_corruption = sum(p['corruption_score'] for p in quality_db.values()) / total_docs
        avg_confidence = sum(p['confidence_score'] for p in quality_db.values()) / total_docs
        
        # Parser performance
        parser_performance = {}
        for profile in quality_db.values():
            parser = profile['parser_used']
            if parser not in parser_performance:
                parser_performance[parser] = {
                    'count': 0,
                    'avg_corruption': 0.0,
                    'avg_confidence': 0.0,
                    'success_rate': 0.0
                }
            
            parser_performance[parser]['count'] += 1
            parser_performance[parser]['avg_corruption'] += profile['corruption_score']
            parser_performance[parser]['avg_confidence'] += profile['confidence_score']
        
        # Calculate averages
        for parser_stats in parser_performance.values():
            count = parser_stats['count']
            parser_stats['avg_corruption'] /= count
            parser_stats['avg_confidence'] /= count
            parser_stats['success_rate'] = parser_stats['avg_confidence']
        
        stats = {
            'total_documents': total_docs,
            'corrupted_count': corrupted_count,
            'high_quality_count': high_quality_count,
            'corruption_rate': corrupted_count / total_docs if total_docs > 0 else 0,
            'high_quality_rate': high_quality_count / total_docs if total_docs > 0 else 0,
            'avg_corruption_score': avg_corruption,
            'avg_confidence_score': avg_confidence,
            'parser_performance': parser_performance,
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
        
        self._save_quality_stats(stats)
    
    def get_quality_profile(self, doc_id: str) -> Optional[ContentQualityProfile]:
        """Get quality profile for a document"""
        quality_db = self._load_quality_database()
        
        if doc_id in quality_db:
            return ContentQualityProfile.from_dict(quality_db[doc_id])
        return None
    
    def get_corrupted_documents(self, corruption_threshold: float = 0.5) -> List[str]:
        """Get list of corrupted document IDs"""
        quality_index = self._load_quality_index()
        
        corrupted_docs = []
        for bucket, doc_ids in quality_index['by_corruption_score'].items():
            bucket_min = float(bucket.split('-')[0])
            if bucket_min >= corruption_threshold:
                corrupted_docs.extend(doc_ids)
        
        return corrupted_docs
    
    def get_high_quality_documents(self, confidence_threshold: float = 0.8) -> List[str]:
        """Get list of high-quality document IDs"""
        quality_index = self._load_quality_index()
        
        high_quality_docs = []
        for bucket, doc_ids in quality_index['by_confidence_score'].items():
            bucket_min = float(bucket.split('-')[0])
            if bucket_min >= confidence_threshold:
                high_quality_docs.extend(doc_ids)
        
        return high_quality_docs
    
    def get_documents_by_parser(self, parser_name: str) -> List[str]:
        """Get documents processed by specific parser"""
        quality_index = self._load_quality_index()
        return quality_index['by_parser'].get(parser_name, [])
    
    def get_documents_needing_reprocessing(self) -> List[str]:
        """Get documents that need reprocessing"""
        quality_index = self._load_quality_index()
        return quality_index['needs_reprocessing']
    
    def get_quality_statistics(self) -> Dict[str, Any]:
        """Get quality statistics"""
        return self._load_quality_stats()
    
    def mark_for_reprocessing(self, doc_id: str):
        """Mark document for reprocessing"""
        profile = self.get_quality_profile(doc_id)
        if profile:
            profile.needs_reprocessing = True
            profile.last_assessed = datetime.now(timezone.utc).isoformat()
            self.save_quality_profile(profile)
    
    def remove_quality_profile(self, doc_id: str):
        """Remove quality profile (for cleanup)"""
        quality_db = self._load_quality_database()
        quality_index = self._load_quality_index()
        
        if doc_id in quality_db:
            # Remove from database
            del quality_db[doc_id]
            
            # Remove from indexes
            for bucket_list in quality_index['by_corruption_score'].values():
                if doc_id in bucket_list:
                    bucket_list.remove(doc_id)
            
            for bucket_list in quality_index['by_confidence_score'].values():
                if doc_id in bucket_list:
                    bucket_list.remove(doc_id)
            
            for parser_list in quality_index['by_parser'].values():
                if doc_id in parser_list:
                    parser_list.remove(doc_id)
            
            for status_list in [quality_index['corrupted_docs'], 
                               quality_index['high_quality_docs'],
                               quality_index['needs_reprocessing']]:
                if doc_id in status_list:
                    status_list.remove(doc_id)
            
            # Save updated data
            self._save_quality_database(quality_db)
            self._save_quality_index(quality_index)
            self._update_quality_statistics()
            
            logger.info(f"Removed quality profile for document: {doc_id}")


class SchemaEnhancedRAG:
    """RAG wrapper with enhanced schema and quality tracking"""
    
    def __init__(self, lightrag_instance, storage_path: str = "/home/ragsvr/projects/ragsystem/rag_storage"):
        self.lightrag = lightrag_instance
        self.quality_tracker = ContentQualityTracker(storage_path)
        
    async def process_document_with_quality_tracking(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """Process document and track quality metrics"""
        start_time = time.time()
        
        try:
            # Process document normally
            result = await self.lightrag.process_document_complete(file_path, **kwargs)
            
            processing_time = time.time() - start_time
            
            # Extract quality metrics (this would need integration with actual analysis)
            # For now, we'll use placeholder values
            doc_id = self._generate_doc_id(file_path)
            
            # Create quality profile
            profile = self.quality_tracker.create_quality_profile(
                doc_id=doc_id,
                file_name=Path(file_path).name,
                file_path=file_path,
                corruption_score=0.0,  # Would be calculated from actual content
                readability_score=0.8,  # Would be calculated from actual content
                information_density=0.7,  # Would be calculated from actual content
                confidence_score=0.85,  # Would be calculated from actual content
                parser_used=kwargs.get('parser', 'mineru'),
                parsing_method=kwargs.get('parse_method', 'auto'),
                processing_time=processing_time,
                content_length=len(str(result)) if result else 0,
                chunk_count=0,  # Would be extracted from actual result
                corruption_patterns=[]  # Would be detected from actual content
            )
            
            # Save quality profile
            self.quality_tracker.save_quality_profile(profile)
            
            return {
                'processing_result': result,
                'quality_profile': profile.to_dict(),
                'processing_time': processing_time
            }
            
        except Exception as e:
            # Create error profile
            processing_time = time.time() - start_time
            doc_id = self._generate_doc_id(file_path)
            
            error_profile = self.quality_tracker.create_quality_profile(
                doc_id=doc_id,
                file_name=Path(file_path).name,
                file_path=file_path,
                corruption_score=1.0,  # Max corruption for failed processing
                readability_score=0.0,
                information_density=0.0,
                confidence_score=0.0,
                parser_used=kwargs.get('parser', 'unknown'),
                parsing_method=kwargs.get('parse_method', 'unknown'),
                processing_time=processing_time,
                content_length=0,
                chunk_count=0,
                corruption_patterns=['processing_failed']
            )
            
            self.quality_tracker.save_quality_profile(error_profile)
            
            raise e
    
    def _generate_doc_id(self, file_path: str) -> str:
        """Generate consistent document ID"""
        return f"doc-{hashlib.md5(file_path.encode()).hexdigest()}"
    
    def get_quality_report(self) -> Dict[str, Any]:
        """Get comprehensive quality report"""
        stats = self.quality_tracker.get_quality_statistics()
        
        return {
            'summary': stats,
            'corrupted_documents': self.quality_tracker.get_corrupted_documents(),
            'high_quality_documents': self.quality_tracker.get_high_quality_documents(),
            'reprocessing_needed': self.quality_tracker.get_documents_needing_reprocessing(),
            'recommendations': self._generate_recommendations(stats)
        }
    
    def _generate_recommendations(self, stats: Dict[str, Any]) -> List[str]:
        """Generate quality improvement recommendations"""
        recommendations = []
        
        if stats['corruption_rate'] > 0.2:
            recommendations.append("High corruption rate detected - consider alternative parsers for DOC files")
        
        if stats['avg_confidence_score'] < 0.5:
            recommendations.append("Low average confidence - review parsing parameters and document quality")
        
        # Parser-specific recommendations
        for parser, perf in stats['parser_performance'].items():
            if perf['avg_corruption'] > 0.3:
                recommendations.append(f"Parser '{parser}' showing high corruption rates - consider tuning or replacement")
        
        if len(self.quality_tracker.get_documents_needing_reprocessing()) > 0:
            recommendations.append("Documents requiring reprocessing detected - run cleanup and reprocess")
        
        return recommendations


# Usage example and testing
def test_schema_enhancement():
    """Test schema enhancement functionality"""
    tracker = ContentQualityTracker()
    
    # Create sample quality profiles
    sample_profiles = [
        tracker.create_quality_profile(
            doc_id="doc-test1",
            file_name="good_document.pdf",
            file_path="/path/to/good_document.pdf",
            corruption_score=0.1,
            readability_score=0.9,
            information_density=0.8,
            confidence_score=0.95,
            parser_used="mineru",
            parsing_method="auto",
            processing_time=2.5,
            content_length=5000,
            chunk_count=10,
            corruption_patterns=[]
        ),
        tracker.create_quality_profile(
            doc_id="doc-test2", 
            file_name="corrupted_document.doc",
            file_path="/path/to/corrupted_document.doc",
            corruption_score=0.8,
            readability_score=0.2,
            information_density=0.1,
            confidence_score=0.15,
            parser_used="libreoffice",
            parsing_method="auto",
            processing_time=1.2,
            content_length=500,
            chunk_count=2,
            corruption_patterns=['repeated_chars', 'chinese_corruption']
        )
    ]
    
    # Save profiles
    for profile in sample_profiles:
        tracker.save_quality_profile(profile)
    
    # Test queries
    print("=== Schema Enhancement Testing ===")
    print(f"Corrupted documents: {tracker.get_corrupted_documents()}")
    print(f"High quality documents: {tracker.get_high_quality_documents()}")
    print(f"Documents needing reprocessing: {tracker.get_documents_needing_reprocessing()}")
    
    # Print statistics
    stats = tracker.get_quality_statistics()
    print(f"\nQuality Statistics:")
    print(f"  Total documents: {stats['total_documents']}")
    print(f"  Corruption rate: {stats['corruption_rate']:.2%}")
    print(f"  Average confidence: {stats['avg_confidence_score']:.3f}")


if __name__ == "__main__":
    test_schema_enhancement()
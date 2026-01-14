import os
import json
from typing import List, Tuple, Optional
from sqlalchemy import create_engine, text, Column, String, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pgvector.sqlalchemy import Vector
from app.models import DocumentChunk, EmbeddingSettings
from app.providers.base import EmbeddingProvider
from app.providers.openai_provider import OpenAIEmbeddingProvider
from app.providers.sentence_transformer_provider import SentenceTransformerProvider

Base = declarative_base()

class DocumentChunkDB(Base):
    """SQLAlchemy model for document chunks with vector embeddings"""
    __tablename__ = 'document_chunks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String(255), nullable=False, index=True)
    chunk_id = Column(Integer, nullable=False)
    doc_name = Column(String(500), nullable=False)
    text = Column(Text, nullable=False)
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    embedding = Column(Vector(None), nullable=False)  # Dimension set at runtime
    
    def to_document_chunk(self) -> DocumentChunk:
        """Convert DB model to DocumentChunk"""
        return DocumentChunk(
            doc_id=self.doc_id,
            doc_name=self.doc_name,
            chunk_id=self.chunk_id,
            text=self.text,
            start_char=self.start_char,
            end_char=self.end_char
        )


class EmbeddingConfig(Base):
    """Store embedding configuration"""
    __tablename__ = 'embedding_config'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(100), nullable=False)
    model = Column(String(200), nullable=False)
    dimension = Column(Integer, nullable=False)


class PostgresVectorStore:
    """PostgreSQL + pgvector based vector store for document embeddings"""
    
    def __init__(self):
        self.embedding_provider: Optional[EmbeddingProvider] = None
        self.embedding_settings: Optional[EmbeddingSettings] = None
        self.engine = None
        self.Session = None
        self.dimension = None
        
        # Get database connection details from environment
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'ragdb')
        db_user = os.getenv('DB_USER', 'raguser')
        db_password = os.getenv('DB_PASSWORD')
        
        if not all([db_host, db_password]):
            raise Exception("Database connection details not found in environment variables")
        
        # Create connection string
        connection_string = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        
        # Create engine
        self.engine = create_engine(connection_string, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        
        # Initialize database
        self._init_database()
        
        print(f"Connected to PostgreSQL database at {db_host}")
    
    def _init_database(self):
        """Initialize database with pgvector extension and tables"""
        with self.engine.connect() as conn:
            # Enable pgvector extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        
        # Create tables
        Base.metadata.create_all(self.engine)
        
        # Load existing embedding configuration
        self.embedding_settings = self._load_embedding_config()
        
        if self.embedding_settings:
            self._initialize_embedding_provider(self.embedding_settings)
            print(f"Loaded existing embedding config: {self.embedding_settings.provider}")
        else:
            print("No existing embedding configuration found")
    
    def _load_embedding_config(self) -> Optional[EmbeddingSettings]:
        """Load embedding configuration from database"""
        session = self.Session()
        try:
            config = session.query(EmbeddingConfig).first()
            if config:
                return EmbeddingSettings(
                    provider=config.provider,
                    model=config.model,
                    dimension=config.dimension
                )
            return None
        finally:
            session.close()
    
    def _save_embedding_config(self, settings: EmbeddingSettings):
        """Save embedding configuration to database"""
        session = self.Session()
        try:
            # Delete existing config
            session.query(EmbeddingConfig).delete()
            
            # Insert new config
            config = EmbeddingConfig(
                provider=settings.provider,
                model=settings.model,
                dimension=settings.dimension
            )
            session.add(config)
            session.commit()
        finally:
            session.close()
    
    def _initialize_embedding_provider(self, settings: EmbeddingSettings):
        """Initialize the embedding provider based on settings"""
        if settings.provider == "openai":
            model = settings.model or "text-embedding-3-small"
            self.embedding_provider = OpenAIEmbeddingProvider(model=model)
        elif settings.provider == "sentence-transformers":
            model = settings.model or "all-MiniLM-L6-v2"
            self.embedding_provider = SentenceTransformerProvider(model_name=model)
        else:
            raise ValueError(f"Unknown embedding provider: {settings.provider}")
        
        self.embedding_settings = settings
        self.dimension = self.embedding_provider.get_dimension()
    
    def set_embedding_provider(self, provider: str, model: Optional[str] = None) -> EmbeddingSettings:
        """
        Set the embedding provider (can only be done before uploading documents)
        
        Args:
            provider: 'openai' or 'sentence-transformers'
            model: Specific model name (optional)
            
        Returns:
            EmbeddingSettings object
            
        Raises:
            Exception: If documents already exist
        """
        if self.is_locked():
            raise Exception("Cannot change embedding provider after documents have been uploaded. Please reset the knowledge base first.")
        
        # Create temporary provider to get dimension
        if provider == "openai":
            model = model or "text-embedding-3-small"
            temp_provider = OpenAIEmbeddingProvider(model=model)
        elif provider == "sentence-transformers":
            model = model or "all-MiniLM-L6-v2"
            temp_provider = SentenceTransformerProvider(model_name=model)
        else:
            raise ValueError(f"Unknown embedding provider: {provider}")
        
        dimension = temp_provider.get_dimension()
        
        # Create settings
        settings = EmbeddingSettings(
            provider=provider,
            model=model,
            dimension=dimension
        )
        
        # Initialize provider
        self._initialize_embedding_provider(settings)
        
        # Save configuration
        self._save_embedding_config(settings)
        
        print(f"Embedding provider set to {provider} (model: {model}, dimension: {dimension})")
        return settings
    
    def get_embedding_settings(self) -> Optional[EmbeddingSettings]:
        """Get current embedding settings"""
        return self.embedding_settings
    
    def is_locked(self) -> bool:
        """Check if embedding provider is locked (documents exist)"""
        session = self.Session()
        try:
            count = session.query(DocumentChunkDB).count()
            return count > 0
        finally:
            session.close()
    
    def add_documents(self, chunks: List[DocumentChunk]):
        """
        Add document chunks to the vector store
        
        Args:
            chunks: List of DocumentChunk objects to add
        """
        if not chunks:
            return
        
        # Check if embedding provider is set
        if self.embedding_provider is None:
            raise Exception("Embedding provider not set. Please set embedding provider before uploading documents.")
        
        # Extract text from chunks
        texts = [chunk.text for chunk in chunks]
        
        # Generate embeddings
        embeddings_list = self.embedding_provider.embed(texts)
        
        # Store in database
        session = self.Session()
        try:
            for chunk, embedding in zip(chunks, embeddings_list):
                db_chunk = DocumentChunkDB(
                    doc_id=chunk.doc_id,
                    chunk_id=chunk.chunk_id,
                    doc_name=chunk.doc_name,
                    text=chunk.text,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    embedding=embedding
                )
                session.add(db_chunk)
            
            session.commit()
            print(f"Added {len(chunks)} chunks to PostgreSQL vector store")
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[DocumentChunk, float]]:
        """
        Search for similar chunks using vector similarity (cosine distance)
        
        Args:
            query: Search query text
            top_k: Number of results to return
            
        Returns:
            List of tuples (DocumentChunk, similarity_score)
        """
        if self.embedding_provider is None:
            raise Exception("Embedding provider not initialized")
        
        # Generate query embedding
        query_embeddings = self.embedding_provider.embed([query])
        query_embedding = query_embeddings[0]
        
        # Search using pgvector
        session = self.Session()
        try:
            # Use cosine distance for similarity search
            # Lower distance = more similar
            results = session.query(
                DocumentChunkDB,
                DocumentChunkDB.embedding.cosine_distance(query_embedding).label('distance')
            ).order_by('distance').limit(top_k).all()
            
            # Convert to DocumentChunk objects with distance scores
            output = []
            for db_chunk, distance in results:
                chunk = db_chunk.to_document_chunk()
                output.append((chunk, float(distance)))
            
            return output
        finally:
            session.close()
    
    def delete_document(self, doc_id: str):
        """
        Delete all chunks for a specific document
        
        Args:
            doc_id: Document ID to delete
        """
        session = self.Session()
        try:
            deleted_count = session.query(DocumentChunkDB).filter(
                DocumentChunkDB.doc_id == doc_id
            ).delete()
            session.commit()
            print(f"Deleted {deleted_count} chunks for document {doc_id}")
        finally:
            session.close()
    
    def reset(self):
        """Reset the entire vector store including embedding configuration"""
        session = self.Session()
        try:
            # Delete all chunks
            session.query(DocumentChunkDB).delete()
            
            # Delete embedding config
            session.query(EmbeddingConfig).delete()
            
            session.commit()
            
            self.embedding_provider = None
            self.embedding_settings = None
            self.dimension = None
            
            print("PostgreSQL vector store reset")
        finally:
            session.close()
    
    def get_all_documents(self) -> List[dict]:
        """Get list of all unique documents in the store"""
        session = self.Session()
        try:
            # Query distinct doc_ids with counts
            results = session.query(
                DocumentChunkDB.doc_id,
                DocumentChunkDB.doc_name,
            ).group_by(
                DocumentChunkDB.doc_id,
                DocumentChunkDB.doc_name
            ).all()
            
            docs = []
            for doc_id, doc_name in results:
                chunk_count = session.query(DocumentChunkDB).filter(
                    DocumentChunkDB.doc_id == doc_id
                ).count()
                
                docs.append({
                    'doc_id': doc_id,
                    'doc_name': doc_name,
                    'num_chunks': chunk_count
                })
            
            return docs
        finally:
            session.close()
    
    def create_hnsw_index(self):
        """Create HNSW index for faster vector search (run after loading data)"""
        session = self.Session()
        try:
            print("Creating HNSW index for faster vector search...")
            session.execute(text(
                f"CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx "
                f"ON document_chunks USING hnsw (embedding vector_cosine_ops)"
            ))
            session.commit()
            print("HNSW index created successfully")
        except Exception as e:
            print(f"Warning: Could not create HNSW index: {e}")
        finally:
            session.close()

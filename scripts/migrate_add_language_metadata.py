#!/usr/bin/env python3
"""
Migration script: Add language metadata to existing Vector DB collections.

This script adds language detection metadata to chunks in existing ChromaDB collections.
Run this once after upgrading to multilingual support.

Usage:
    python scripts/migrate_add_language_metadata.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import chromadb
from chromadb.config import Settings
from rich.console import Console
from rich.progress import track

from lecture_forge.config import Config
from lecture_forge.utils import detect_language, get_language_name

console = Console()


def migrate_collection(collection_path: Path):
    """
    Add language metadata to a collection.

    Args:
        collection_path: Path to ChromaDB collection directory
    """
    collection_name = collection_path.name
    console.print(f"\n[cyan]Processing collection:[/cyan] {collection_name}")

    try:
        # Initialize ChromaDB client
        client = chromadb.PersistentClient(
            path=str(collection_path),
            settings=Settings(anonymized_telemetry=False),
        )

        # Get collection
        collection = client.get_collection(name=collection_name)

        # Get all documents
        all_data = collection.get(include=["documents", "metadatas"])

        if not all_data or not all_data.get("documents"):
            console.print(f"[yellow]⚠️  No documents found in collection[/yellow]")
            return

        documents = all_data["documents"]
        metadatas = all_data["metadatas"]
        ids = all_data["ids"]

        console.print(f"[green]✅ Found {len(documents)} documents[/green]")

        # Check if language metadata already exists
        sample_metadata = metadatas[0] if metadatas else {}
        if "language" in sample_metadata:
            console.print(f"[yellow]⚠️  Language metadata already exists, skipping[/yellow]")
            return

        # Detect language for each document
        console.print("[cyan]Detecting languages...[/cyan]")
        updated_metadatas = []
        language_stats = {}

        for doc, metadata in track(
            zip(documents, metadatas),
            total=len(documents),
            description="Processing chunks",
        ):
            # Detect language
            lang = detect_language(doc, default="unknown")

            # Update metadata
            updated_metadata = metadata.copy() if metadata else {}
            updated_metadata["language"] = lang

            updated_metadatas.append(updated_metadata)

            # Track statistics
            language_stats[lang] = language_stats.get(lang, 0) + 1

        # Update collection with new metadata
        console.print("[cyan]Updating collection...[/cyan]")
        collection.update(ids=ids, metadatas=updated_metadatas)

        console.print(f"[green]✅ Successfully migrated {len(documents)} chunks[/green]")

        # Display language statistics
        console.print("\n[cyan]Language distribution:[/cyan]")
        for lang, count in sorted(language_stats.items(), key=lambda x: x[1], reverse=True):
            lang_name = get_language_name(lang)
            percentage = (count / len(documents)) * 100
            console.print(f"  • {lang_name}: {count} chunks ({percentage:.1f}%)")

    except Exception as e:
        console.print(f"[red]❌ Error processing collection: {e}[/red]")
        import traceback

        traceback.print_exc()


def main():
    """Main migration function."""
    console.print("\n[bold]🔄 LectureForge - Language Metadata Migration[/bold]\n")

    # Find all vector DB collections
    vector_db_path = Config.VECTOR_DB_PATH

    if not vector_db_path.exists():
        console.print(f"[red]❌ Vector DB path not found: {vector_db_path}[/red]")
        return

    collections = [d for d in vector_db_path.iterdir() if d.is_dir()]

    if not collections:
        console.print(f"[yellow]⚠️  No collections found in {vector_db_path}[/yellow]")
        return

    console.print(f"[green]Found {len(collections)} collection(s):[/green]")
    for collection in collections:
        console.print(f"  • {collection.name}")

    # Confirm migration
    console.print("\n[yellow]This will add language metadata to all existing chunks.[/yellow]")
    response = input("Continue? [y/N]: ")

    if response.lower() != "y":
        console.print("[red]Migration cancelled[/red]")
        return

    # Migrate each collection
    console.print("\n[cyan]Starting migration...[/cyan]")

    for collection_path in collections:
        migrate_collection(collection_path)

    console.print("\n[green]✅ Migration complete![/green]")
    console.print("\n[dim]You can now use multilingual Q&A with cross-lingual search.[/dim]")


if __name__ == "__main__":
    main()

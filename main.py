from fastapi import FastAPI, Depends, HTTPException, Query
from sqlmodel import Session, select, SQLModel
from typing import List, Optional
from datetime import datetime

from models import Book, BookCreate, BookUpdate
from database import get_session, engine

app = FastAPI(title="Bookstore API", version="1.0")

# Create tables on startup
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

# ============================================
# POST /books - Create a new book
# ============================================
@app.post("/books", response_model=Book, status_code=201)
def create_book(book: BookCreate, session: Session = Depends(get_session)):
    """
    Create a new book in the inventory.
    
    - **title**: Book title (required)
    - **author**: Book author (required)
    - **isbn**: Unique ISBN (required)
    - **published_year**: Year published (1000-current year)
    - **price**: Price (must be > 0)
    - **stock**: Quantity in stock (>= 0)
    - **available**: Availability status (default: True)
    """
    # Validate published_year
    current_year = datetime.now().year
    if not (1000 <= book.published_year <= current_year):
        raise HTTPException(400, f"Published year must be between 1000 and {current_year}")
    
    # Validate price
    if book.price <= 0:
        raise HTTPException(400, "Price must be greater than 0")
    
    # Validate stock
    if book.stock < 0:
        raise HTTPException(400, "Stock must be greater than or equal to 0")
    
    # Check if ISBN already exists
    existing = session.exec(select(Book).where(Book.isbn == book.isbn)).first()
    if existing:
        raise HTTPException(400, "Book with this ISBN already exists")
    
    new_book = Book(**book.dict())
    session.add(new_book)
    session.commit()
    session.refresh(new_book)
    return new_book

# ============================================
# GET /books - List all books with filters
# ============================================
@app.get("/books", response_model=List[Book])
def list_books(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    title: Optional[str] = None,
    author: Optional[str] = None,
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_stock: Optional[int] = Query(None, ge=0),
    max_stock: Optional[int] = Query(None, ge=0),
    available_only: Optional[bool] = None,
    session: Session = Depends(get_session)
):
    """
    List all books with optional filtering.
    
    - **title**: Filter by title (partial match)
    - **author**: Filter by author (partial match)
    - **min_price**: Minimum price
    - **max_price**: Maximum price
    - **min_stock**: Minimum stock quantity
    - **max_stock**: Maximum stock quantity
    - **available_only**: Show only available books
    """
    query = select(Book)
    
    if title:
        query = query.where(Book.title.contains(title))
    if author:
        query = query.where(Book.author.contains(author))
    if min_price is not None:
        query = query.where(Book.price >= min_price)
    if max_price is not None:
        query = query.where(Book.price <= max_price)
    if min_stock is not None:
        query = query.where(Book.stock >= min_stock)
    if max_stock is not None:
        query = query.where(Book.stock <= max_stock)
    if available_only is not None:
        query = query.where(Book.available == available_only)
    
    return session.exec(query.offset(skip).limit(limit)).all()

# ============================================
# GET /books/{book_id} - Get book by ID
# ============================================
@app.get("/books/{book_id}", response_model=Book)
def get_book(book_id: int, session: Session = Depends(get_session)):
    """
    Get a specific book by its ID.
    """
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return book

# ============================================
# PATCH /books/{book_id} - Update a book
# ============================================
@app.patch("/books/{book_id}", response_model=Book)
def update_book(
    book_id: int,
    book_update: BookUpdate,
    session: Session = Depends(get_session)
):
    """
    Partially update a book's information.
    """
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    
    # Validate fields before updating
    update_data = book_update.dict(exclude_unset=True)
    
    if "published_year" in update_data:
        current_year = datetime.now().year
        if not (1000 <= update_data["published_year"] <= current_year):
            raise HTTPException(400, f"Published year must be between 1000 and {current_year}")
    
    if "price" in update_data and update_data["price"] <= 0:
        raise HTTPException(400, "Price must be greater than 0")
    
    if "stock" in update_data and update_data["stock"] < 0:
        raise HTTPException(400, "Stock must be greater than or equal to 0")
    
    if "isbn" in update_data:
        existing = session.exec(
            select(Book).where(Book.isbn == update_data["isbn"], Book.id != book_id)
        ).first()
        if existing:
            raise HTTPException(400, "Book with this ISBN already exists")
    
    # Apply updates
    for key, value in update_data.items():
        setattr(book, key, value)
    
    book.updated_at = datetime.utcnow()
    session.commit()
    session.refresh(book)
    return book

# ============================================
# DELETE /books/{book_id} - Delete a book
# ============================================
@app.delete("/books/{book_id}", status_code=204)
def delete_book(book_id: int, session: Session = Depends(get_session)):
    """
    Delete a book from the inventory.
    """
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    
    session.delete(book)
    session.commit()
    return None

# ============================================
# GET /books/search - Search books
# ============================================
@app.get("/books/search", response_model=List[Book])
def search_books(
    q: str = Query(..., min_length=1, description="Search query for title or author"),
    session: Session = Depends(get_session)
):
    """
    Search for books by title or author (case-insensitive partial match).
    """
    query = select(Book).where(
        (Book.title.contains(q)) | (Book.author.contains(q))
    )
    return session.exec(query).all()

# ============================================
# Health Check Endpoint
# ============================================
@app.get("/health")
def health_check():
    """Check if API is running."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

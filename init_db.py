import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from main import engine, Base
Base.metadata.create_all(engine)
print("Database tables created successfully!")

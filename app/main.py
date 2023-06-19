import pathlib
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from cassandra.query import SimpleStatement
from cassandra.cqlengine.management import sync_table

from . import (config, models, db, ml, schema)

app = FastAPI()
settings = config.get_settings()

BASE_DIR = pathlib.Path(__file__).resolve().parent

MODEL_DIR = BASE_DIR.parent / "models"
SMS_SPAM_MODEL_DIR = MODEL_DIR / "spam-sms"
MODEL_PATH = SMS_SPAM_MODEL_DIR / "spam-model.h5"
TOKENIZER_PATH = SMS_SPAM_MODEL_DIR / "spam-classifer-tokenizer.json"
METADATA_PATH = SMS_SPAM_MODEL_DIR / "spam-classifer-metadata.json"

AI_MODEL = None
DB_SESSION = None
SMSInference = models.SMSinference

@app.on_event("startup")
def on_startup():
    global AI_MODEL, DB_SESSION
    AI_MODEL = ml.AIModel(
        model_path= MODEL_PATH,
        tokenizer_path= TOKENIZER_PATH,
        metadata_path= METADATA_PATH,
    )
    DB_SESSION = db.get_session()
    sync_table(SMSInference)

@app.get("/") # /?q=this is awesome
def read_index(q:Optional[str] = None):
    return {"Hello": "World"}

@app.post("/") # /?q=this is awesome #use post method when touching the database
def create_inference(query:schema.Query):
    global AI_MODEL
    preds_dict = AI_MODEL.predict_text(query.q)
    top = preds_dict.get('top') # {label: , confidence:}
    data = {"query": query.q, **top}
    obj = SMSInference.objects.create(**data)
    # NoSQL -> cassandra -> DataStax AstraDB
    return obj

@app.get("/inferences")
def list_inference():
    q = SMSInference.objects.all()
    print(q)
    return list(q)

@app.get("/inferences/{my_uuid}")
def read_inference(my_uuid):
    obj = SMSInference.objects.get(uuid=my_uuid)
    return obj

def fetch_rows(
        stmt:SimpleStatement, 
        fetch_size:int = 25, 
        session=None):
    stmt.fetch_size = fetch_size
    result_set = session.execute(stmt)
    yield "uuid,label,confidence,query,model_version\n"
    while True:
        for row in result_set.current_rows:
            yield f"{row['uuid']},{row['label']},{row['confidence']},{row['query']},{row['model_version']}\n"
        if not result_set.has_more_pages:
            break
        result_set = session.execute(stmt, paging_state=result_set.paging_state)

@app.get("/dataset")
def export_inference():
    global DB_SESSION
    cql_query = "SELECT * FROM spam_inferences.smsinference LIMIT 10000"
    statement = SimpleStatement(cql_query)
    # rows = DB_SESSION.execute(cql_query)
    return StreamingResponse(fetch_rows(statement, 25, DB_SESSION))

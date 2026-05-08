from pydantic import BaseModel, Field, model_validator, ConfigDict

class Ref(BaseModel) :
    ref : str 
    
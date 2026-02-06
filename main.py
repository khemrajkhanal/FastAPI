from pydantic import BaseModel, Field, computed_field
from fastapi import FastAPI, Path, HTTPException, Query
from fastapi.responses import JSONResponse
import json
from typing import Annotated, Literal, Optional

DATA_FILE = 'patient.json'

class Patient(BaseModel):
    id: Annotated[str, Field(..., description='ID of the patient',examples=['P001'])]
    name: Annotated[str, Field(..., description='Name of the patient')]
    city: Annotated[str, Field(..., description='City where the patient is living')]
    age: Annotated[int, Field(..., gt=0, description='Age of the patient')]
    gender: Annotated[Literal['male','female','others'], Field(..., description='Gender of the patient')]
    height: Annotated[float, Field(..., gt=0, description='Height of the patient in meters')]
    weight: Annotated[float, Field(..., description='Weight of the patients in Kgs')]

    @computed_field
    @property
    def bmi(self) -> float:
        bmi = round(self.weight/(self.height**2),2)
        return bmi

    @computed_field
    @property
    def verdict(self) -> str:
        if self.bmi < 18.5:
            return 'Underweight'
        elif self.bmi < 25:
            return 'Healthy weight'
        elif self.bmi < 30:
            return 'Overweight'
        else:
            return 'Obese'


class PatientUpdate(BaseModel):
    name: Annotated[Optional[str], Field(default=None)]
    city: Annotated[Optional[str], Field(default=None)]
    age: Annotated[Optional[int], Field(default=None, gt=0)]
    gender: Annotated[Optional[Literal['male','female','others']], Field(default=None)]
    height: Annotated[Optional[float], Field(default=None, gt=0)]
    weight: Annotated[Optional[float], Field(default=None, gt=0)]


def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}  # Return empty dict if file doesn't exist
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail='Data file is corrupted')

def save_data(data):
    with open(DATA_FILE,'w') as f:
        json.dump(data, f,indent=2)


app = FastAPI()

@app.get('/')
def hello():
    return{'message':'Patient Record System'}

@app.get('/home')
def home():
    return{'message':'This as API that shows Patients records'}

@app.get('/patients')
def patients():
    data = load_data()
    return data

@app.get('/patients/{patient_id}')
def view_patient(patient_id:str = Path(..., description='Insert patient ID here', example='P001')):
    data = load_data()
    if patient_id in data:
        return data[patient_id]
    raise HTTPException(status_code=404, detail='Patient not Found!')

@app.get('/sort')
def sort_patients(sort_by: str = Query(..., description='Sort on the basis of height, weight and bmi')
                  , order: str = Query('asc', description='sort in asc or desc order')):
    valid_fields = ['height','weight','bmi']

    if sort_by not in valid_fields:
        raise HTTPException(status_code=400, detail=f'Invalid selection from {valid_fields}')

    if order not in ['asc','desc']:
        raise HTTPException(status_code=400, detail=f'Invalid order between asc or desc')

    data = load_data()

    order_value = True if order == 'desc' else False
    sorted_data = sorted(data.values(), key=lambda x: x.get(sort_by,0), reverse=order_value )
    return sorted_data

@app.post('/create')
def create_patient(patient: Patient):
    #load existing data
    data = load_data()
    #checkif the patient already exist
    if patient.id in data:
        raise HTTPException(status_code=400, detail='Patient already exist')
    #new patient add to the database
    data[patient.id] = patient.model_dump(exclude={'id'})

    #save into json file
    save_data(data)
    return JSONResponse(status_code=201, content={'message':'Patient created successfully'})

@app.put('/edit/{patient_id}')
def update_patient(patient_id: str, patient_update: PatientUpdate):
    data = load_data()
    if patient_id not in data:
        raise HTTPException(status_code=404, detail='Patient not found')
    existing_patient_info = data[patient_id]
    updated_patient_info = patient_update.model_dump(exclude_unset=True)

    for key, value in updated_patient_info.items():
        existing_patient_info[key] = value

    #for updating bmi and verdict if patient changes weight or height
    existing_patient_info['id'] = patient_id
    patient_pydantic_obg = Patient(**existing_patient_info)
    existing_patient_info = patient_pydantic_obg.model_dump(exclude={'id'})

    data[patient_id] = existing_patient_info
    save_data(data)
    return JSONResponse(status_code=200, content={'message':'Patient Updated'})

@app.delete('/delete/{patient_id}')
def delete_patient(patient_id: str = Path(..., description='Enter patient id that you want to delete')):
    data = load_data()
    if patient_id not in data:
        raise HTTPException(status_code=404, detail='Patient not found')
    del data[patient_id]
    save_data(data)
    return JSONResponse(status_code=200, content={'message': 'Patient deleted successfully'})

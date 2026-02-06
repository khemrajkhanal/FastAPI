from pydantic import BaseModel, Field, computed_field
from fastapi import FastAPI, Path, HTTPException, Query
import json
from typing import Annotated, Literal, Optional


class Patient(BaseModel):
    id: Annotated[str, Field(..., description='ID of the patient', examples=['P001'])]
    name: Annotated[str, Field(..., description='Name of the patient')]
    city: Annotated[str, Field(..., description='City where the patient is living')]
    age: Annotated[int, Field(..., gt=0, description='Age of the patient')]
    gender: Annotated[Literal['male', 'female', 'others'], Field(..., description='Gender of the patient')]
    height: Annotated[float, Field(..., gt=0, description='Height of the patient in meters')]
    weight: Annotated[float, Field(..., gt=0, description='Weight of the patients in Kgs')]

    @computed_field
    @property
    def bmi(self) -> float:
        bmi = round(self.weight / (self.height ** 2), 2)
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
    gender: Annotated[Optional[Literal['male', 'female', 'others']], Field(default=None)]
    height: Annotated[Optional[float], Field(default=None, gt=0)]
    weight: Annotated[Optional[float], Field(default=None, gt=0)]


DATA_FILE = 'patient.json'


def load_data():
    """Load patient data from JSON file"""
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail='Data file is corrupted')


def save_data(data):
    """Save patient data to JSON file"""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Failed to save data: {str(e)}')


def renumber_patients(data):
    """Renumber all patient IDs sequentially starting from P001"""
    if not data:
        return {}

    # Convert to list and sort by existing ID numbers
    patients_list = []
    for patient_id, patient_data in data.items():
        patients_list.append((patient_id, patient_data))

    # Sort by the numeric part of the ID
    patients_list.sort(key=lambda x: int(x[0][1:]))

    # Create new dictionary with renumbered IDs
    renumbered_data = {}
    for index, (old_id, patient_data) in enumerate(patients_list, start=1):
        new_id = f"P{index:03d}"  # Format as P001, P002, etc.
        renumbered_data[new_id] = patient_data

    return renumbered_data


def get_next_patient_id(data):
    """Generate the next sequential patient ID"""
    if not data:
        return "P001"

    # Extract all numeric parts and find the maximum
    max_id = max(int(pid[1:]) for pid in data.keys())
    return f"P{max_id + 1:03d}"


app = FastAPI(title="Patient Record System", version="1.0.0")


@app.get('/')
def hello():
    return {'message': 'Patient Record System'}


@app.get('/home')
def home():
    return {'message': 'This is an API that shows Patients records'}


@app.get('/patients')
def get_all_patients():
    """Get all patients"""
    data = load_data()
    return data


@app.get('/patients/{patient_id}')
def view_patient(patient_id: str = Path(..., description='Insert patient ID here', example='P001')):
    """Get a specific patient by ID"""
    data = load_data()
    if patient_id in data:
        return data[patient_id]
    raise HTTPException(status_code=404, detail='Patient not found!')


@app.get('/sort')
def sort_patients(
        sort_by: str = Query(..., description='Sort on the basis of height, weight and bmi'),
        order: str = Query('asc', description='Sort in asc or desc order')
):
    """Sort patients by height, weight, or BMI"""
    valid_fields = ['height', 'weight', 'bmi']

    if sort_by not in valid_fields:
        raise HTTPException(
            status_code=400,
            detail=f'Invalid field. Must be one of: {", ".join(valid_fields)}'
        )

    if order not in ['asc', 'desc']:
        raise HTTPException(status_code=400, detail='Order must be "asc" or "desc"')

    data = load_data()
    order_value = (order == 'desc')
    sorted_data = sorted(data.values(), key=lambda x: x.get(sort_by, 0), reverse=order_value)
    return sorted_data


@app.post('/create', status_code=201)
def create_patient(patient: Patient):
    """Create a new patient with auto-generated ID"""
    data = load_data()

    # Auto-generate the next patient ID
    new_patient_id = get_next_patient_id(data)

    # Add new patient to the database
    data[new_patient_id] = patient.model_dump(exclude={'id'})

    # Save into JSON file
    save_data(data)

    return {
        'message': 'Patient created successfully',
        'patient_id': new_patient_id
    }


@app.put('/edit/{patient_id}')
def update_patient(patient_id: str, patient_update: PatientUpdate):
    """Update an existing patient"""
    data = load_data()

    if patient_id not in data:
        raise HTTPException(status_code=404, detail='Patient not found')

    existing_patient_info = data[patient_id]
    updated_patient_info = patient_update.model_dump(exclude_unset=True)

    # Update only provided fields
    for key, value in updated_patient_info.items():
        existing_patient_info[key] = value

    # Recalculate BMI and verdict if weight or height changed
    existing_patient_info['id'] = patient_id
    patient_pydantic_obj = Patient(**existing_patient_info)
    existing_patient_info = patient_pydantic_obj.model_dump(exclude={'id'})

    data[patient_id] = existing_patient_info
    save_data(data)

    return {
        'message': 'Patient updated successfully',
        'patient_id': patient_id,
        'patient': existing_patient_info
    }


@app.delete('/delete/{patient_id}')
def delete_patient(patient_id: str = Path(..., description='Enter patient ID that you want to delete')):
    """Delete a patient and renumber all subsequent patients"""
    data = load_data()

    if patient_id not in data:
        raise HTTPException(status_code=404, detail='Patient not found')

    # Save deleted patient info
    deleted_patient = data[patient_id]

    # Delete the patient
    del data[patient_id]

    # Renumber all patients sequentially
    renumbered_data = renumber_patients(data)

    # Save the renumbered data
    save_data(renumbered_data)

    return {
        'message': 'Patient deleted successfully and IDs renumbered',
        'deleted_patient': deleted_patient,
        'new_patient_count': len(renumbered_data)
    }
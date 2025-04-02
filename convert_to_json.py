import pandas as pd
import json

# Read the Excel file
df = pd.read_excel('Master Hospitals Dataset.xlsx')

# Clean the data
df = df.fillna('')

# Group by state
hospitals_by_state = {}
for state, group in df.groupby('STATE'):
    hospitals_by_state[state] = group.to_dict(orient='records')

# Save to JSON file
with open('hospital_data.json', 'w') as f:
    json.dump(hospitals_by_state, f)

print("Conversion complete. Data saved to hospital_data.json") 
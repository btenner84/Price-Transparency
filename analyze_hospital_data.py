import pandas as pd

# Read the Excel file
df = pd.read_excel('Master Hospitals Dataset.xlsx')

# Display basic information
print(f'Shape: {df.shape} (rows, columns)')

print('\nColumns:')
for col in df.columns:
    print(f'- {col}')

print('\nSample Data:')
print(df.head(5).to_string())

print('\nData Types:')
print(df.dtypes)

print('\nSummary Statistics:')
print(df.describe().to_string())

# Check for missing values
print('\nMissing Values:')
missing = df.isnull().sum()
print(missing[missing > 0].to_string()) 
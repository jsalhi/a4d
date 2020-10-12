import pandas
import sys

df = pandas.read_csv(sys.argv[1])

print(df)
adf = df.where(df['Name'] == '*')
print(adf)

dfn = df.where(df['Name'] != '*')
dfn = dfn.groupby(['Violation'])[['Black/F']].sum()
print(dfn)


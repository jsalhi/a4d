import pandas

all_dfs = [] 
for i in range(2010, 2020):
    fname = str(i) + '.pdf_out.csv'
    df = pandas.read_csv(fname)
    df['Year'] = i
    all_dfs.append(df)

all_df = pandas.concat(all_dfs)
all_df.to_csv('all.csv')

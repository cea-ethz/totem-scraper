import pandas as pd

SEP = ';'

df1 = pd.read_csv('elements.csv', sep=SEP, engine='python')
df2 = pd.read_csv('components.csv', sep=SEP, engine='python')

# duplicated_elements = df1.groupby(['Element Name', 'Layer', 'Component Name', 'Application']).size().reset_index(name='match_count')
# duplicated_elements = duplicated_elements[duplicated_elements['match_count'] > 1]
# if not duplicated_elements.empty:
#     raise ValueError(f"Found duplicated elements: {duplicated_elements}")

# duplicated_components = df2.groupby(['Component Name', 'Application', 'LCI-ID', 'Material']).size().reset_index(name='match_count')
# duplicated_components = duplicated_components[duplicated_components['match_count'] > 1]
# if not duplicated_components.empty:
#     raise ValueError(f"Found duplicated components: {duplicated_components}")

merged_df = pd.merge(df1, df2, on=['Component Name', 'Application'], how='left', indicator=True)

unmatched_df = merged_df[merged_df['_merge'] == 'left_only']
unmatched_df = unmatched_df[['Component Name', 'Application']].drop_duplicates()
unmatched_df.to_csv('missing_components.csv', index=False, sep=SEP)

merged_df = merged_df.drop(columns=['_merge'])
merged_df.to_csv('totem_data.csv', index=False, sep=SEP)
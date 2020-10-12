import re
import sys
import pandas

from enum import Enum
from pdfreader import SimplePDFViewer

PageType = Enum('PageType', 'summary officer unknown')

FOOTER = 'Citations - Violations By Sex and Race'
OFFICER_PAGE_HEADER = 'Citations - Violations By Sex and Race - By Officer'
SUMMARY_PAGE_HEADER = 'Citations - Violations By Sex and Race - By Violation'

ETHNICITIES = ['Asian', 'Black', 'White', 'Indigenous American', 'Unknown']
GENDERS = ['F', 'M', 'U']

OFFICER_NAME_PATTERN = r'[A-Z,\s]+'
OFFICER_MARKDOWN_DELIMITER = '23\.18 .* Td'

# Handles number strings with commas e.g. 3,246. Ignore leading zeros (e.g. '07' for BAC violations).
def is_digit(st):
    if len(st) > 1 and st[0] == '0':
        return False
    return st.replace(',', '').isdigit()

# Get integer value of a string with commas.
def str_value(st):
    return int(st.replace(',', ''))

# Return page type based on the header displayed at the top of the page.
def get_page_type(page_strings):
    page_header = page_strings[0]
    if page_header == OFFICER_PAGE_HEADER:
        return PageType.officer
    elif page_header == SUMMARY_PAGE_HEADER:
        return PageType.summary
    return PageType.unknown

# Parse a row of data from a section of violation data.
# Returns:
#   # Index (of page_strings) of beginning of next data row for this section. None if reached end of a page/section.
#   # Index of "Totals" row if it is encountered.
#   # Label of row (violation description).
#   # Data points corresponding to violation description (corresponds to breakdowns by gender/ethnicity). None
#   if encountering Total counts row on page.
#
def parse_data_row(start_index, page_strings, name="*"):
    i = start_index
    label_parts = []
    # Sometimes the row labels are parsed as multiple strings, so they need to be joined until we hit real data.
    while(True):
        st = page_strings[i]
        if is_digit(st):
            break
        label_parts.append(st)
        i += 1
    violation_description = ' '.join(label_parts) 

    # In case part of the row label is parsed as a digit. Should be 16 values per row.
    if is_digit(page_strings[i + 16]):
        print(page_strings)
        raise Exception('Improperly parsed row label')
    
    # Reached end of entire summary section. Doesn't return Total data because it may be incomplete/missing.
    if 'Total' in violation_description:
        return None, i-1, violation_description, None
 
    # Skip redundant 'Total' value.
    i += 1 

    # Should be exactly 15 datapoints per row.
    data = [name, violation_description]
    for ethnicity in ETHNICITIES:
        for gender in GENDERS:
            value = str_value(page_strings[i])
            data.append(value)
            i += 1
   
    # Reached end of page.
    if page_strings[i + 1] == FOOTER:
        return None, None,  violation_description, data
 
    return i, None, violation_description, data

# Parses a pdf page detailing offense data broken down by ethnicity, with totals.
#
# page_strings(list<string>): a list of the parsed elements in the rendered pdf page.
def parse_summary_page(page_strings, df=None):
    # Skip header information since pdfreader doesn't do a great job of automatically parsing the table.
    page_strings = page_strings[24:]

    i = 0
    while(i is not None):
        i, _, violation_description, data = parse_data_row(i, page_strings)
        if data is not None:
            df.loc[len(df)] = data

# This does this in kind of a hacky way but it seems to work.
def parse_officer_names(page_markdown):
    # Parse markdown to markdown flags that appear before names. Throw away previous content and grab next ~1000
    # characters.
    sections = re.split(OFFICER_MARKDOWN_DELIMITER, page_markdown)[1:]
    name_sections = []
    for section in sections:
        section_content = section[:1000].strip()
        lines = section_content.splitlines()
   
        i = 0
        name_parts = []
        while(True):
            line = lines[i]
            if line[0] == "(":
                name_part = line.split(")")[0][1:].strip()
                if not re.fullmatch(OFFICER_NAME_PATTERN, name_part):
                    break
                name_parts.append(name_part)
                i += 1
            else:
                break
            i += 1
        if len(name_parts) > 0:
            name_sections.append(name_parts)
    return name_sections

def find_officer_data_index(start_index, page_strings, name_parts):
    i = start_index
    while(True):
        st = page_strings[i]
        found_officer_data = True
        for ind in range(len(name_parts)):
            if page_strings[i + ind] != name_parts[ind]:
                found_officer_data = False
                break 
        if found_officer_data:
            return i + len(name_parts) 
        i += 1 
    return None
    

def parse_officer_page(page_markdown, page_strings, df=None):
    all_name_parts = parse_officer_names(page_markdown)
    for officer_name_parts in all_name_parts:
        officer_data_index = find_officer_data_index(0, page_strings, officer_name_parts)
        i = officer_data_index
        while i is not None:
            next_row_index, total_index, violation_description, data = parse_data_row(i, page_strings, name=''.join(officer_name_parts))
            if data is not None:
                df.loc[len(df)] = data
            i = next_row_index

def main():
    fname = sys.argv[1]
    f = open(fname, "rb")
    viewer = SimplePDFViewer(f)   
    viewer.render()

    page_strings = viewer.canvas.strings
    page_markdown = viewer.canvas.text_content
    page_type = get_page_type(page_strings)

    df = pandas.DataFrame(columns = ['Name', 'Violation'] +  ['/'.join([e, g]) for e in ETHNICITIES for g in GENDERS])

    while(page_type != PageType.unknown):        
        if page_type == PageType.officer:
            parse_officer_page(page_markdown, page_strings, df=df)
        elif page_type == PageType.summary:
            parse_summary_page(page_strings, df=df)
        
        # Paginate, get next page information.
        try:
            viewer.next()
        except Exception as e:
            print("Error paginating (probably done): ", e)
            break
        viewer.render()
        page_strings = viewer.canvas.strings
        page_markdown = viewer.canvas.text_content
        page_type = get_page_type(page_strings)

    df.to_csv(fname + '_out.csv')
main()

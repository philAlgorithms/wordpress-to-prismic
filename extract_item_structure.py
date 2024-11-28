import sys
from lxml import etree
from collections import defaultdict

def print_structure(element, indent=0):
    """
    Recursively prints the structure of an XML element.
    
    :param element: The current XML element.
    :param indent: The current indentation level.
    """
    print('  ' * indent + f"<{element.tag}>")
    for child in element:
        print_structure(child, indent + 1)
    print('  ' * indent + f"</{element.tag}>")

def extract_first_item_structure(xml_file_path):
    """
    Extracts and prints the structure of the first <item> element in the XML file.
    
    :param xml_file_path: Path to the WordPress export XML file.
    """
    # Define the namespace map
    ns = {
        'wp': 'http://wordpress.org/export/1.2/'
    }
    
    # Create an iterparse context
    context = etree.iterparse(xml_file_path, events=('start', 'end'), encoding='utf-8')
    context = iter(context)
    
    # Get the root element
    event, root = next(context)
    
    for event, elem in context:
        if event == 'end' and elem.tag == 'item':
            print("Structure of the first <item> element:")
            print_structure(elem)
            break  # Exit after processing the first <item>
        
        # It's important to clear the element to save memory
        if event == 'end':
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
    
    # Clean up the root element
    root.clear()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python extract_item_structure.py path_to_wordpress_export.xml")
        sys.exit(1)
    
    xml_file = sys.argv[1]
    extract_first_item_structure(xml_file)
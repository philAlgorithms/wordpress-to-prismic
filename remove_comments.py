from lxml import etree

# Path to the input and output XML files
input_file = 'wordpress-export.xml'
output_file = 'wordpress-prismic-updated.xml'

def remove_comments(input_file, output_file):
    # Parse the XML file
    parser = etree.XMLParser(recover=True)  # Allow for minor XML errors
    tree = etree.parse(input_file, parser)

    # Find and remove all <wp:comment> elements
    for comment in tree.xpath('//wp:comment', namespaces={'wp': 'http://wordpress.org/export/1.2/'}):
        comment.getparent().remove(comment)

    # Write the updated XML back to a new file
    # Use `method="xml"` and specify encoding as UTF-8, without HTML escaping
    with open(output_file, 'wb') as f:
        tree.write(f, pretty_print=True, xml_declaration=True, encoding='UTF-8', method="xml")

    print(f'Updated XML saved as {output_file}')

if __name__ == '__main__':
    remove_comments(input_file, output_file)

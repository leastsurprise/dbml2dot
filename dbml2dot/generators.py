import math
from textwrap import dedent
import pydbml.classes
import pydot
import re
import networkx as nx
import uuid
from itertools import cycle
from palettable.colorbrewer.qualitative import Set3_8 # for header groups
from utils import debug

from __main__ import encoded_tooltips


def extract_color_and_tooltip_from_note(note):
    match = re.search(r'^.*?COLOU?R:\s*(\d+)\b(.*?)$', note, re.IGNORECASE)
    if match:
        index = int(match.group(1))
        color = Set3_8.hex_colors[index % len(Set3_8.colors)]
        tooltip = match.group(2).strip()
        return color, tooltip
    return None, None



def generate_table_label(name: str, attributes: list[str], header_color: tuple, tooltip: str):
    attribute_list: list[str] = []
    if header_color is not None:
        header_color = ' bgcolor="' + header_color + '" '
    else:
        header_color = ''
    for attr in attributes:
        td_attributes = ''
        match = re.search(r'^(.*?)(PORT=)(.*?)(BGCOLOR=)("#.+?")(.*)$', attr, re.IGNORECASE)
        if match:
            attr = f"{match.group(1)}{match.group(6)}"
            td_attributes += f" port={match.group(3)}"
            td_attributes += f" bgcolor={match.group(5)}"
        match = re.search(r'^(.*?)( tooltip=")(.+?)(")(.*)$', attr, re.IGNORECASE)
        if match:
            attr = f"{match.group(1)}{match.group(5)}"
            k = str(uuid.uuid4()).replace('-','x')
            encoded_tooltips.append({'key': k, 'text': attr, 'tooltip':match.group(3).strip()})
            attr = k
        attribute_list += [f"""<TR><TD align="left"{td_attributes}>{attr}</TD></TR>"""]
    attribute_list_str = "\n".join(attribute_list)
    attr = name
    if tooltip:
        k = str(uuid.uuid4()).replace('-','')
        k = k * 10
        k = k[:len(name)]
        encoded_tooltips.append({'key': k, 'text': attr, 'tooltip':'<title>' + tooltip.strip() + '</title>'})
        attr = k
    return dedent(f'''
        <<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">
        <TR><TD{header_color}><B>{attr}</B></TD></TR><HR></HR>
        {attribute_list_str}
        </TABLE>>''').strip().replace('\n', '\n\t')



def generate_column_node(name: str, column_attributes: pydbml.classes.Column, enums: list[str], reference: pydbml.classes.Reference):
    not_null_string = "" if column_attributes.not_null or column_attributes.pk else "?"
    col_string = f"{name}{not_null_string}"
    if column_attributes.pk:
        col_string = f"<B>{col_string}</B>"
    if column_attributes.unique:
        col_string = f"<I>{col_string}</I>"
    attribute_str = f"{col_string} : {column_attributes.type}"

    enums_used = []
    if str(column_attributes).strip() in enums:
        enums_used += [str(column_attributes)]

    # is this column either end of the reference?
    if reference is not None and (name == reference.col1[0].name or name == reference.col2[0].name):
        if hasattr(reference, 'note'):
            colors, tooltip = extract_color_and_tooltip_from_note(reference.note.text)
            if colors and 'BGCOLOR' not in attribute_str:
                attribute_str = f"<TABLE BORDER='0' CELLBORDER='1' CELLSPACING='0' CELLPADDING='4'><TR><TD BGCOLOR='{colors.column_color}'>{attribute_str}</TD></TR></TABLE>"
        else:
            attribute_str += 'PORT="' + column_attributes.port_nbr + '"'
            attribute_str += 'BGCOLOR="' + reference.column_color + '"'

    return attribute_str, enums_used


def get_reference(column: pydbml.classes.Column, references: list[pydbml.classes.Reference]):
    for ref in references:
        this_col = column.name
        col1_name = ref.col1[0].name
        col2_name = ref.col2[0].name
        # the idea here is just to return a single reference of possibly many
        # there is a recursion issue in other versions of the code because a ref contains a col contains a ref contains a col......
        # We need this ref so we know to express the port for linking, or set the header colour in the
        # html-esque .dot coding.
        if this_col in col1_name or this_col in col2_name:
            return ref
    return None


def generate_table_nodes(name: str, contents: pydbml.classes.Table, enums: list[str], references: list[pydbml.classes.Reference]) -> tuple[    pydot.Node, list[pydot.Edge]]:
    debug(f"{name}: {contents}")

    header_color, toolip = extract_color_and_tooltip_from_note(contents.note.text) 
    
    for reference in references:
        #reference.edge_color, reference.column_color = extract_next_colour_pair()
        reference.edge_color, reference.column_color = ('#000000','#FFFFFF')
        reference.port1 = reference.col1[0].name
        reference.port2 = reference.col2[0].name
        
    attributes = []
    enums_used = []
    for item in contents.columns:
        column_name = item.name
        note = item.note
        column_attributes: pydbml.classes.Column = item 
        attribute_str, enums_used_by_column = generate_column_node(column_name, column_attributes, enums, get_reference(column_attributes, references))
        if note:
            attribute_str += f' tooltip="{note.text}"'
        attributes += [attribute_str]
        enums_used += enums_used_by_column

    node: pydot.Node = pydot.Node(
        name,
        label=generate_table_label(name, attributes, header_color, toolip)
    )

    edges: list[pydot.Edge] = []
    for enum_used in enums_used:
        debug(f"{enum_used} is in enums")
        edges += [pydot.Edge(enum_used, name, style="invis")]

    return node, edges


def generate_graph_from_dbml(dbml: pydbml.PyDBML) -> pydot.Graph:
    graph = pydot.Graph()
    graph.set_node_defaults(fontname="Bitstream Vera Sans", fontsize=14, shape="plain")
    graph.set_edge_defaults(fontname="Bitstream Vera Sans", fontsize=8, labeldistance=2, color="grey")
    graph.set_graph_defaults(rankdir='LR', nodesep="0.5", pad="0.5", ranksep="2", overlap="false")
    graph.set_graph_defaults(splines='true')
    enums = []
    for enum in dbml.enums:
        enum: pydbml.classes.Enum = enum

        graph.add_node(pydot.Node(
            enum.name,
            label=generate_table_label(f"<I>Enum</I><BR></BR>{enum.name}", enum.items)
        ))

        enums.append(enum.name.strip())

    debug(f"{enums=}")
    debug("Tables:", list(dbml.table_dict.keys()))

    # assign each column a unique port number to allow column level liniking not just table linking
    port_nbr = 0
    for table_name, table_contents in dbml.table_dict.items():
         for column in table_contents.columns:
            port_nbr += 1
            column.port_nbr = str(port_nbr)

    for table_name, table_contents in dbml.table_dict.items():
        table_name = table_contents.name # not full_name
        node, edges = generate_table_nodes(table_name, table_contents, enums, dbml.refs)

        graph.add_node(node)
        for edge in edges:
            graph.add_edge(edge)

    for reference in dbml.refs:
        reference: pydbml.classes.Reference = reference

        orig: pydbml.classes.Column = reference.col1
        dest: pydbml.classes.Column = reference.col2
        orig = orig[0].name
        dest = dest[0].name

        label_len = (len(dest) + len(orig)) 
        ml = int(math.sqrt(1+label_len/2))

        if reference.table1.name == reference.table2.name:
            debug("Origin and destination are identical", reference.table1.name)
            for i in range(label_len // 8):
                graph.add_edge(pydot.Edge(reference.table1.name, reference.table2.name, style="invis"))
                # graph.


        if reference.type == '-':
            graph.add_edge(pydot.Edge(
                reference.table1.name + ':' + reference.col1[0].port_nbr,
                reference.table2.name + ':' + reference.col2[0].port_nbr,
                minlen=ml, arrowhead="none", arrowtail="none",
                color=reference.edge_color
            ))
        elif reference.type == '<':
            graph.add_edge(pydot.Edge(
                reference.table1.name + ':' + reference.col1[0].port_nbr,
                reference.table2.name + ':' + reference.col2[0].port_nbr,
                arrowtail="none", arrowhead="crow", 
                color=reference.edge_color, # minlen=ml
            ))
        elif reference.type == '>':
            graph.add_edge(pydot.Edge(
                reference.table1.name + ':' + reference.col1[0].port_nbr,
                reference.table2.name + ':' + reference.col2[0].port_nbr,
                arrowhead="none", arrowtail="crow",
                color=reference.edge_color #, minlen=ml
            ))
        elif reference.type == '<>':
            graph.add_edge(pydot.Edge(
                reference.table1.name + ':' + reference.col1[0].port_nbr,
                reference.table2.name + ':' + reference.col2[0].port_nbr,
                arrowhead="crow", arrowtail="crow", dir='both',
                color=reference.edge_color #, minlen=ml
            ))

    # graph.set_simplify(True)
    graph.set_type("digraph")

    return graph


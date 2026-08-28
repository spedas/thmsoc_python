def url_construct_web_query(
        web_scheme:str='https',
        web_netloc:str='',
        web_path:str='',
        query_list:list[tuple[str,str|list[str]]]=[],
        query_separator:str='&',
        web_fragment:str=''
        ) -> str:
    '''
    Returns a constructed web query URL 
    from input query parameters. Each 
    element of the query_list argument 
    is assumed to be a tuple containing 
    the query parameter name and an 
    iterable with one or more elements, 
    which will be populated into the 
    query individually. The query_list 
    argument does not accept dict by 
    default because web queries may be 
    order-sensitive.
    '''
    web_query=''
    if len(query_list) > 0:
        web_query += "?"
        for query_idx in range(len(query_list)):
            # New query field
            # Get query name and value list
            query_name,values = query_list[query_idx]
            # After the first query, separate the queries
            if query_idx > 0:
                web_query += query_separator
            # Even queries without values get query names
            web_query += query_name
            # If the query has a value, use an equals:
            if len(values) > 0:
                web_query += "="
                if type(values) != list:
                    values = [values]
                # Then place each element after the equals, comma separated:
                for value_idx in range(len(values)):
                    if value_idx > 0:
                        web_query += query_separator + query_name + "=" #","
                    web_query += values[value_idx]    
    return web_scheme+"://"+web_netloc+web_path+web_query+web_fragment
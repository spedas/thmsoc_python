from cdflib import cdfwrite
from cdflib import cdfread
from pathlib import Path
import numpy as np

"""
Needs to accomplish the following:

Create mastercdf from template with new name and associated CDF attributes/variable names
Update CDF metadata using input argument ()
Apply metadata from a mastercdf file onto another CDF file (update data CDFs)
"""
def set_cdf_variable(cdf_variable:dict) -> dict:
    """
    Converts data_val data type/dtype based on cdf_datatype. If data_val is None, applies a default null value to the variable data.

    Inspired by _convert_nptype from cdflib.cdfwrite

    returns modified dict with corrected variable data dtype, pad value, and fillval
    """
    cdf_default_pad_values = {
        "CDF_UINT1":254, # 11
        "CDF_INT2":-32767, # 2
        "CDF_UINT2":65534, # 12
        "CDF_INT4":-2147483647, # 4
        "CDF_UINT4":4294967294, # 14
        "CDF_EPOCH":0.0, # 31
        "CDF_EPOCH16":[0.0, 0.0], #32
    }
    cdf_default_pad_values.update(dict.fromkeys(["CDF_BYTE", "CDF_INT1"], -127)) # 1, 41
    cdf_default_pad_values.update(dict.fromkeys(["CDF_INT8", "CDF_TIME_TT2000"], -9223372036854775807)) # 8, 33
    cdf_default_pad_values.update(dict.fromkeys(["CDF_REAL4","CDF_FLOAT","CDF_REAL8","CDF_DOUBLE"], -1.0e30)) # 21, 44, 22, 45
    cdf_default_pad_values.update(dict.fromkeys(["CDF_CHAR", "CDF_UCHAR"]," ")) # 51, 52
    
    # after matching the variable datatype, set appropriate variable datatype, pad value, and fillval
    if cdf_variable["VarInfo"]["Data_Type"] in [51,52]:
        cdf_variable["VarInfo"]["Pad"]=str(cdf_default_pad_values[cdf_variable["VarInfo"]["Data_Type_Description"]])
    elif cdf_variable["VarInfo"]["Data_Type"] in [21,44,22,45,31,32]:
        cdf_variable["VarInfo"]["Pad"]=float(cdf_default_pad_values[cdf_variable["VarInfo"]["Data_Type_Description"]])
    else: 
        cdf_variable["VarInfo"]["Pad"]=int(cdf_default_pad_values[cdf_variable["VarInfo"]["Data_Type_Description"]])

    if "FILLVAL" in cdf_variable["VarAttrs"].keys():
        if cdf_variable["VarAttrs"]["FILLVAL"] is None:
            if cdf_variable["VarInfo"]["Data_Type"] in [21,44,22,45,31,32]:
                cdf_variable["VarAttrs"]["FILLVAL"] = np.array([np.nan])
            else:
                cdf_variable["VarAttrs"]["FILLVAL"] = np.array([cdf_variable["VarInfo"]["Pad"]])
        else:
            if isinstance(cdf_variable["VarAttrs"]["FILLVAL"],list):
                cdf_variable["VarAttrs"]["FILLVAL"] = np.array(cdf_variable["VarAttrs"]["FILLVAL"])
            elif not isinstance(cdf_variable["VarAttrs"]["FILLVAL"],np.ndarray):
                cdf_variable["VarAttrs"]["FILLVAL"] = np.array([cdf_variable["VarAttrs"]["FILLVAL"]])

    if cdf_variable["VarInfo"]["Last_Rec"] >= 0:
        if cdf_variable["VarData"] is None:
            if "FILLVAL" in cdf_variable["VarAttrs"].keys():
                cdf_variable["VarData"] = cdf_variable["VarAttrs"]["FILLVAL"]
            else:
                if cdf_variable["VarInfo"]["Data_Type"] in [21,44,22,45,31,32]:
                    cdf_variable["VarData"] = np.array([np.nan])
                else:
                    cdf_variable["VarData"] = np.array([cdf_variable["VarInfo"]["Pad"]])
        else:
            if isinstance(cdf_variable["VarData"],list):
                cdf_variable["VarData"] = np.array(cdf_variable["VarData"])
            elif not isinstance(cdf_variable["VarData"],np.ndarray):
                cdf_variable["VarData"] = np.array([cdf_variable["VarData"]])
    # TODO: throw error if vardata and fillval are not of type np.ndarray
    match cdf_variable["VarInfo"]["Data_Type"]:
        case 1 | 41:
            dtype_toset = np.int8            
        case 2:
            dtype_toset = np.int16 
        case 4: 
            #dtype_toset = np.int32 
            dtype_toset = np.int64 
        case 8 | 33:
            dtype_toset = np.int64 
        case 11:
            dtype_toset = np.uint8 
        case 12:
            dtype_toset = np.uint16
        case 14:
            dtype_toset = np.uint32
        case 21 | 44:
            #dtype_toset = np.float32
            dtype_toset = np.float64
        case 22 | 45 | 31:
            dtype_toset = np.float64
        case 32:
            dtype_toset = np.complex128
        case 51 | 52:
            dtype_toset = np.str_
        case _:
            raise ValueError(f"ERROR! Variable Datatype not recognized. Please check variable: {cdf_variable["VarInfo"]["Variable"]}")

    for attrname in ["FILLVAL","VALIDMIN","VALIDMAX"]:
        if attrname in cdf_variable["VarAttrs"].keys():
            cdf_variable["VarAttrs"][attrname] = dtype_toset(cdf_variable["VarAttrs"][attrname])        
    if cdf_variable["VarInfo"]["Last_Rec"] >= 0:
        if dtype_toset == np.str_:
            # Instead, encode as utf-8:
            str_array=cdf_variable["VarData"]
            np.strings.encode(cdf_variable["VarData"], encoding='utf-8')
            cdf_variable["VarData"]=str_array
        else:
            cdf_variable["VarData"] = dtype_toset(cdf_variable["VarData"])
    return cdf_variable    

def compare_dict(
        dict1:dict,
        dict2:dict,
        name1:str,
        name2:str,
        verbose:bool=False):
    """
    Recursively identifies differences between two dicts

    Parameters
    ----------
    verbose : bool

    """
    # TODO: return string containing list of differences, as this might be used for error handling
    abort_comp = False
    if len(set(dict1.keys())-set(dict2.keys())) > 0:
        if verbose:
            print(f"The following keys from {name1} are absent from {name2}:")
            for key in set(dict1.keys())-set(dict2.keys()):
                print(key)
        abort_comp = True
    if len(set(dict2.keys())-set(dict1.keys())) > 0:
        if verbose:
            print(f"The following keys from {name2} are absent from {name1}:")
            for key in set(dict2.keys())-set(dict1.keys()):
                print(key)
        abort_comp = True
    if abort_comp:
        return
    else:
        dict_keys = dict1.keys()
        for dict_key in dict_keys:
            val_1 = dict1[dict_key]
            val_2 = dict2[dict_key]
            if type(val_1) != type(val_2):
                #if not (dict_key in key_ignore_none and (dict1[dict_key] is None or dict2[dict_key] is None)):        
                print(f"Type mismatch between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"].")
                if verbose:
                    print(f">> Type of {name1}[\"{dict_key}\"]: {type(dict1[dict_key])}")
                    print(f">> Type of {name2}[\"{dict_key}\"]: {type(dict2[dict_key])}")
                return
            # Value types should be the same
            match type(val_1).__name__:
                case "dict":
                    compare_dict(
                        val_1,
                        val_2,
                        f"{name1}[\"{dict_key}\"]",
                        f"{name2}[\"{dict_key}\"]",
                        verbose)
                case "list":
                    if not (len(val_1) == len(val_2) == 0):
                        if val_1 != val_2:
                            #if not (dict_key in key_ignore_none and (dict1[dict_key] is None or dict2[dict_key] is None)):        
                            if len(val_1) != len(val_2):
                                print(f"List mismatch between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                                print(f">> List values have differing length: {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                                abort_comp = True
                            else:   
                                if all([isinstance(x,dict) for x in val_1]) and all([isinstance(x,dict) for x in val_2]):
                                    # types of val_1 and val_2 are list[dict], (likely attributes list) so they cannot simply be sorted
                                    # convert to list of tuples and use set comparison instead:
                                    val_1_list_tuple=[]
                                    for element in val_1:
                                        for key in element.keys():
                                            val_1_list_tuple.append((key,element[key]))
                                    val_2_list_tuple=[]
                                    for element in val_2:
                                        for key in element.keys():
                                            val_2_list_tuple.append((key,element[key]))
                                    if set(val_1_list_tuple) != set(val_2_list_tuple):
                                        print(f"List mismatch; differing elements found between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                                        abort_comp = True     
                                else:
                                    # lengths should be the same; check for set equivalency:
                                    val_set_1 = val_1.sort()
                                    val_set_2 = val_2.sort()
                                    if val_set_1 != val_set_2:
                                        # the sets are not just reordered; they have different elements
                                        print(f"List mismatch between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                                        n_diff = 0
                                        for i in range(len(dict1[dict_key])):
                                            if val_1[i] != val_2[i]:
                                                n_diff+=1
                                        print(f">> Found {n_diff} differences out of {len(val_1)} elements.") 
                                        abort_comp = True
                case "array":
                    if not np.array_equal(val_1,val_2,equal_nan=True):
                        print(f"Array mismatch between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                        if verbose:
                            print(f">> Value of {name1}[\"{dict_key}\"]: {dict1[dict_key]}")
                            print(f">> Value of {name2}[\"{dict_key}\"]: {dict2[dict_key]}")
                        abort_comp = True
                case "ndarray":
                    if val_1.dtype.name != val_2.dtype.name:
                        print(f"NDArray dtype mismatch between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                        if verbose:
                            print(f">> dtype of {name1}[\"{dict_key}\"]: {val_1.dtype.name}")
                            print(f">> dtype of {name2}[\"{dict_key}\"]: {val_2.dtype.name}")
                        abort_comp = True
                    elif val_1.dtype.name not in ['str64','str672','str576']:
                        if not np.array_equal(val_1,val_2,equal_nan=True):
                            #if verbose:
                            #    print(f">> Value of {name1}[\"{dict_key}\"]: {dict1[dict_key]}")
                            #    print(f">> Value of {name2}[\"{dict_key}\"]: {dict2[dict_key]}")
                            abort_comp = True
                    else: 
                        if not np.array_equal(val_1,val_2):
                            print(f"NDArray mismatch between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                            #if verbose:
                            #    print(f">> Value of {name1}[\"{dict_key}\"]: {dict1[dict_key]}")
                            #    print(f">> Value of {name2}[\"{dict_key}\"]: {dict2[dict_key]}")
                            abort_comp = True
                case _:
                    if val_1 != val_2:
                        #if not (dict_key in key_ignore_none and (dict1[dict_key] is None or dict2[dict_key] is None)):                        
                        print(f"Value mismatch between {name1}[\"{dict_key}\"] and {name2}[\"{dict_key}\"]")
                        if verbose:
                            print(f">> Value of {name1}[\"{dict_key}\"]: {dict1[dict_key]}")
                            print(f">> Value of {name2}[\"{dict_key}\"]: {dict2[dict_key]}")
                        abort_comp = True          
    if abort_comp:
        return
    return

def dict_number_pair(dict_to_convert:dict) -> dict:
    """
    For each key in dict_to_listify, convert value to list containing value instead
    """
    for key in dict_to_convert.keys():
        if type(dict_to_convert[key]) is not dict:
            key_val_dict = {0:""}
            if isinstance(dict_to_convert[key],list):
                for i in range(len(dict_to_convert[key])):
                    key_val_dict[i]=dict_to_convert[key][i]
            else:
                key_val_dict[0] = dict_to_convert[key]
            dict_to_convert[key] = key_val_dict
    return dict_to_convert

def cdf_get_struct(cdf_path:Path) -> dict:
    """
    Returns dict containing CDF data and metadata. Mimics the output of cdf_readcdf in IDL. Assumes all variables are zvariables
    
    Creates a dictionary of the form:
    cdf_metadata = {
        "CDFInfo": CDFInfo()
        "GlobalAttrs": dict
        "Variables": {
            "VARNAME": {
                "VarInfo": VDRInfo(),
                "VarAttrs": dict,
                "VarData": Union[str, np.ndarray]
                "VDRInfo": VDR
            }
        }
    }
    The "CDFInfo" key contains the output of cdf_info() and can be used for writing new CDFs
    The "GlobalAttrs" key contains the output of globalattsget()
    The "Variables" dict contains keys where each key is a variable name and corresponds to a dict containing "VarInfo" (containing the output of varinq()), "VarAttrs" (containing the output of varattsget()), and "VarData" (containing the output of varget())
    """
    cdf=cdfread.CDF(str(cdf_path))
    cdf_metadata={
        "CDFInfo":(cdf.cdf_info()).__dict__,
        "GlobalAttrs":dict_number_pair(cdf.globalattsget()),
        "Variables":{}
    }
    for zvar in cdf_metadata["CDFInfo"]["zVariables"]:
        var_dict = {}
        var_dict["VarInfo"] = (cdf.varinq(zvar)).__dict__
        var_dict["VarAttrs"] = cdf.varattsget(zvar)
        try:
            var_dict["VarData"] = cdf.varget(zvar)
        except ValueError:
            var_dict["VarData"] = None
        # Update variable dict to enforce correct datatypes, pad value, and fillval
        cdf_metadata["Variables"][zvar] = set_cdf_variable(var_dict)    
    # TODO: Verify that the zvar struct variable entries are not empty, and throw an error if they are
    return cdf_metadata

def cdf_update_struct(cdf_struct:dict,updates:dict) -> dict:
    """
    Update cdf struct dict using updates in updates dict. Return updated cdf struct dict
    """
    for update_action in updates.keys():
        update_action_obj=updates[update_action]
        match update_action:
            case "update_logicalsource":
                # queues a bunch of updates and calls cdf_update_struct recursively.
                # TODO: first check if updates includes new time resolution
                old_logicalsource=cdf_struct["GlobalAttrs"]["Logical_source"][0]
                new_logicalsource=update_action_obj
                new_changes = {
                    "update_attr":{"global":{}},
                    "rename_var":{}
                }
                new_changes["update_attr"]["global"].update({"Logical_source":new_logicalsource})
                if old_logicalsource in cdf_struct["GlobalAttrs"]["Logical_file_id"][0]:
                    id_suffix = (cdf_struct["GlobalAttrs"]["Logical_file_id"][0].split(old_logicalsource))[-1]
                    new_changes["update_attr"]["global"].update({"Logical_file_id":new_logicalsource+id_suffix})
                # remove level from logical source before checking variable names:
                var_format=old_logicalsource
                new_var_format=new_logicalsource
                if "l2_" in old_logicalsource:
                    var_format="".join(old_logicalsource.split("l2_",1))
                if "l2_" in new_logicalsource:
                    new_var_format="".join(new_logicalsource.split("l2_",1))
                for var in cdf_struct["Variables"].keys():
                    if var_format in var:
                        var_suffix = (var.split(var_format))[-1]
                        new_changes["rename_var"].update({var:new_var_format+var_suffix})                      
                cdf_struct = cdf_update_struct(cdf_struct,new_changes)
            case "rename_var":
                rename_dict = update_action_obj
                new_changes = {
                    "update_var":{},
                    "remove_var":[],
                    "update_var_dependencies":rename_dict
                }
                for var_oldname in rename_dict.keys():
                    var_newname = rename_dict[var_oldname]
                    old_var_value=cdf_struct["Variables"][var_oldname]
                    new_changes["update_var"].update({var_newname:old_var_value})
                    new_changes["remove_var"].append(var_oldname)
                # Update CDFInfo:
                renamed_vars=rename_dict.copy()
                # Include variable names which are not changed (value and key are the same):
                for v in cdf_struct["CDFInfo"]["zVariables"]:
                    renamed_vars.setdefault(v,v)
                # Write updated names to a list, preserving order of original zvariables list:
                new_zVar_list = [renamed_vars[v] for v in cdf_struct["CDFInfo"]["zVariables"]]
                cdf_struct["CDFInfo"]["zVariables"] = new_zVar_list
                # Call cdf_update_struct recursively to apply variable and variable attribute changes:
                cdf_struct = cdf_update_struct(cdf_struct,new_changes)
            case "update_var_dependencies":
                dep_updates_dict = update_action_obj
                new_changes = {
                    "update_attr":{}
                }
                for varname in cdf_struct["Variables"].keys():
                    var_attrs = cdf_struct["Variables"][varname]["VarAttrs"]
                    # check variable attributes for dependencies:
                    var_attrs_str_vals = [v for v in var_attrs.values() if type(v) is str]
                    outdated_dependencies = list(set(dep_updates_dict.keys()) & set(var_attrs_str_vals))
                    if len(outdated_dependencies) > 0:
                        new_changes["update_attr"].update({varname:{}})
                        # variable contains dependency in its attributes    
                        for attr in var_attrs.keys():
                            if type(var_attrs[attr]) is str:
                                new_dep_val = dep_updates_dict.get(var_attrs[attr])
                                if new_dep_val is not None:
                                    new_changes["update_attr"][varname].update({attr:new_dep_val})
                cdf_struct = cdf_update_struct(cdf_struct,new_changes)
            case "rename_attr":
                new_changes = {
                    "update_attr":{},
                    "remove_attr":{}
                    }
                for scope in update_action_obj.keys():
                    new_changes["update_attr"].update({scope:{}})
                    new_changes["remove_attr"].update({scope:{}})              
                    for attr_oldname in update_action_obj[scope].keys():
                        match scope:
                            case "global":
                                attr_dict = dict_number_pair(cdf_struct["GlobalAttrs"].get(attr_oldname))
                            case _:
                                # assume scope is variable
                                attr_dict = cdf_struct["Variables"][scope]["VarAttrs"].get(attr_oldname)
                        if attr_dict is not None:
                            new_changes["update_attr"][scope].update({update_action_obj[scope][attr_oldname]:attr_dict})
                            new_changes["remove_attr"][scope].append(attr_oldname)
                cdf_struct = cdf_update_struct(cdf_struct,new_changes)
            case "append_attr":
                new_changes = {}
                for scope in update_action_obj.keys():
                    for attr_name in update_action_obj[scope]:
                        match scope:
                            case "global":
                                attr_val = cdf_struct["GlobalAttrs"].get(attr_name)
                            case _:
                                attr_val = cdf_struct["Variables"][scope]["VarAttrs"].get(attr_name)
                        if type(attr_val) is not list:
                            attr_val = [attr_val]
                        attr_vals_toappend = update_action_obj[scope].get(attr_name)
                        if type(attr_vals_toappend) is not list:
                            attr_vals_toappend = [attr_vals_toappend]
                        for item_to_append in attr_vals_toappend:
                            attr_val.append(item_to_append)
                        new_changes["update_attr"][scope].update({attr_name:attr_val})
                cdf_struct = cdf_update_struct(cdf_struct,new_changes)
            case "update_var":
                cdf_struct["Variables"].update(update_action_obj)
            case "remove_var":
                for var_to_remove in update_action_obj:
                    cdf_struct["Variables"].pop(var_to_remove)
            case "update_attr":
                for scope in update_action_obj.keys():
                    match scope:
                        case "global":
                            cdf_struct["GlobalAttrs"].update(dict_number_pair(update_action_obj[scope]))
                        case _:
                            cdf_struct["Variables"][scope]["VarAttrs"].update(update_action_obj[scope])
            case "remove_attr":
                for scope in update_action_obj.keys():
                    for attr_name in update_action_obj[scope]:
                        match scope:
                            case "global":
                                cdf_struct["GlobalAttrs"].pop(attr_name)
                            case _:
                                cdf_struct["Variables"][scope]["VarAttrs"].pop(attr_name)
            case "update_CDFInfo_VarInfo":
                # Update CDFInfo Attributes:
                att_list_g=[]
                for ga_key in cdf_struct["GlobalAttrs"].keys():
                    # Update CDFInfo Global Attributes:
                    att_list_element = {ga_key:'Global'}
                    if att_list_element not in att_list_g:
                        att_list_g.append(att_list_element)
                att_list_v=[]
                for v in cdf_struct["Variables"].keys():
                    # for each variable, update the VarInfo Variable attribute to be the current name of the CDF variable:
                    cdf_struct["Variables"][v]["VarInfo"]["Variable"] = v
                    # Update CDFInfo Variable Attributes:
                    for va_key in cdf_struct["Variables"][v]["VarAttrs"].keys():
                        att_list_element = {va_key:'Variable'}
                        if att_list_element not in att_list_v:
                            att_list_v.append(att_list_element)
                cdf_struct["CDFInfo"]["Attributes"] = att_list_g + att_list_v
                # Reorder variables according to zvariables list:
                cdf_struct["Variables"] = {varname: cdf_struct["Variables"][varname] for varname in cdf_struct["CDFInfo"]["zVariables"]}
            case _:
                raise ValueError(f"ERROR: Update action {update_action} not recognized.")
    # Do one last check to make sure global attribute values are all indexed dictionaries:
    cdf_struct["GlobalAttrs"] = dict_number_pair(cdf_struct["GlobalAttrs"])
    # return cdf_struct:
    return cdf_struct

def cdf_generate(
        output_cdf_fp:Path,
        output_cdf_struct:dict,
        updates:dict | None):
    """
    Creates updated CDF using original data, if original CDF exists. Applies updates according to updates dict.

    data is contained in output_cdf_struct dict, so it will be used to write new cdf from scratch
    """
    copy_right = (
        "\nCommon Data Format (CDF)\nhttps://cdf.gsfc.nasa.gov\n"
        + "Space Physics Data Facility\n"
        + "NASA/Goddard Space Flight Center\n"
        + "Greenbelt, Maryland 20771 USA\n"
        + "(User support: gsfc-cdf-support@lists.nasa.gov)\n"
    )
    # Update metadata 
    if updates is not None:
        # Ensure CDFInfo reflects created CDF
        output_cdf_struct["CDFInfo"]["CDF"] = output_cdf_fp
        output_cdf_struct["CDFInfo"]["Copyright"] = copy_right

        updates.update({"update_CDFInfo_VarInfo":""})
        output_cdf_struct = cdf_update_struct(output_cdf_struct,updates)

    # TODO: on error, delete created CDF file and raise alert.
    cdf_output = cdfwrite.CDF(
        path=output_cdf_fp,
        cdf_spec=output_cdf_struct["CDFInfo"],
        delete=True)
    # Write contents of updated output_cdf_struct to cdf_output_write:
    # Global attributes:
    cdf_output.write_globalattrs(globalAttrs=output_cdf_struct.get("GlobalAttrs"))
    # Variable attributes:
    for var in output_cdf_struct["Variables"].keys():
        cdf_output.write_var(
            var_spec=output_cdf_struct["Variables"][var]["VarInfo"],
            var_attrs=output_cdf_struct["Variables"][var]["VarAttrs"],
            var_data=output_cdf_struct["Variables"][var]["VarData"])
    # That should be it; we can close the CDF
    cdf_output.close()

    # Verify update worked correctly:
    updated_cdf_struct = cdf_get_struct(output_cdf_fp)
    compare_dict(output_cdf_struct,updated_cdf_struct,"output_cdf_struct","updated_cdf_struct",verbose=True)
    return

def cdf_updater(
        mastercdf_fp:str | Path | None, 
        outputcdf_fp: str | Path | list[str | Path] | None = None, 
        updates: dict | None = None):
    # TODO: optional path for difference error logging?
    # TODO: should use a temporary directory to write the file, make the updates, and then to quit if any differences are detected between the updated CDF structure and the written CDF file. If there's an error, the temporary file should be deleted. If no differences are detected, then that temporary CDF should be written to the given outputcdf_fp location. 
    # TODO: handle updating from list in parallel
    """
    Updates CDF metadata for each CDF path in outputcdf_fp, using a safety layer to prevent update errors. 
    
    First, it checks if the outputcdf_fp points to an already existing CDF file; if it does 
    
    updates {
        "update_logicalsource": "new_logicalsource_name"
        "rename_var": {
            "var_oldname":"var_newname"
        }
        "update_var":{
            "varname":var_dict
        }
        "remove_var":[varname1, varname2, ...]
        "rename_attr":{
            "global":{
                attr_oldname:attr_newname
                }
            "varname":{
                attr_oldname:attr_newname
            }
        }
        "update_attr":{
            "global":global_atts_dict
            "varname":var_atts_dict
        }
        "append_attr":{
            "global":global_atts_dict
            "varname":var_atts_dict
        }
        "remove_attr":{
            "global":global_atts_list
            "varname":var_atts_list
        }
    }
    Set output_cdf_strs to mastercdf_str to update mastercdf in-place
    """
    # Load mastercdf metadata
    # Check if output CDF already exists; if not, create output cdf from mastercdf
    # load output cdf metadata 
    # apply updates to output cdf metadata in the following order of priority:
    #       * update logical source change by renaming attributes and variables
    #       * rename variables by copying replaced variables under the new name and by deleting the replaced variables
    #       * update attributes using corresponding method
    #       * 
    # apply metadata changes to output cdf 
    
    # Want to construct a CDF metadata (global and variable attributes) dictionary to update and then use to write the output CDF. The mastercdf can then be closed and possibly rewritten, using the metadata.
    
    # Create mastercdf metadata dict from mastercdf file:
    
    if outputcdf_fp is None:
        print("Output CDF filepath not provided; updating mastercdf in-place instead...")
        if mastercdf_fp is not None:
            if type(mastercdf_fp) != Path:
                mastercdf_fp = Path(mastercdf_fp)
                outputcdf_fp = mastercdf_fp
        else:
            raise ValueError("ERROR! Either the mastercdf_fp or the outputcdf_fp must be provided!")
        
    if isinstance(outputcdf_fp,str) or isinstance(outputcdf_fp,Path):
        outputcdf_fp = [outputcdf_fp]

    if isinstance(outputcdf_fp,list):
        print("Updating CDFs...")    
        for outputcdf_fp_current in outputcdf_fp:
            if isinstance(outputcdf_fp_current,str):
                outputcdf_fp_current=Path(outputcdf_fp_current)
            if outputcdf_fp_current.exists():
                print("CDF exists; getting existing CDF structure...")
                # get outputcdf data
                cdf_output = cdf_get_struct(outputcdf_fp_current)
            else:
                print("CDF does not exist; using mastercdf struct as template...")
                if mastercdf_fp is not None:
                    if type(mastercdf_fp) != Path:
                        mastercdf_fp = Path(mastercdf_fp)
                else:
                    raise ValueError("ERROR! Target CDF does not exist, but mastercdf_fp is not provided! Please provide a filepath to the mastercdf so that a CDF can be created from it.")
                if not mastercdf_fp.exists():
                    raise ValueError("ERROR! mastercdf_fp does not point to a valid existing filepath! Please check that the mastercdf_fp is correct.")
                print("Getting mastercdf struct...")
                cdf_master = cdf_get_struct(mastercdf_fp)
                # set outputcdf data as mastercdf data
                cdf_output = cdf_master.copy()
            print(f"Generating new CDF for {str(outputcdf_fp_current)}...")
            cdf_generate(
                output_cdf_fp=outputcdf_fp_current,
                output_cdf_struct=cdf_output,
                updates=updates)
    print("Done!")
    return

if __name__ == "__main__":
    Path("C:/Users/DC/Documents/Projects/thmsoc_svn/src/mastercdfs/thg/thg_l2_mag_lrv_1min_00000000_v01.cdf").unlink(missing_ok=True)
    Path("C:/Users/DC/Documents/Projects/thmsoc_svn/src/mastercdfs/thg/thg_l2_mag_snkq_1min_00000000_v01.cdf").unlink(missing_ok=True)
    cdf_updater(
        mastercdf_fp="C:/Users/DC/Documents/Projects/thmsoc_svn/src/mastercdfs/thg/thg_l2_mag_lrv_00000000_v01.cdf", 
        outputcdf_fp="C:/Users/DC/Documents/Projects/thmsoc_svn/src/mastercdfs/thg/thg_l2_mag_lrv_1min_00000000_v01.cdf", 
        updates={
            "update_logicalsource":"thg_l2_mag_lrv_1min",
            "update_attr":{
                "global":{
                    'Time_resolution':'1 minute',
                    'Generation_date':'2026-07-28',
                    'spase_DatasetResourceID':'',
                    'Logical_source_description':'Higher latitude chain (Lat 64.2, Long 338.3), Ground-based Vector Magnetic Field at Leirvogur, Iceland, 1 minute resolution data.',
                    'MODS':'Rev-2026-07-28 (dcarpenter): CDF template created.'
                }
            }
        })
    cdf_updater(
        mastercdf_fp="C:/Users/DC/Documents/Projects/thmsoc_svn/src/mastercdfs/thg/thg_l2_mag_snkq_00000000_v01.cdf", 
        outputcdf_fp="C:/Users/DC/Documents/Projects/thmsoc_svn/src/mastercdfs/thg/thg_l2_mag_snkq_1min_00000000_v01.cdf", 
        updates={
            "update_logicalsource":"thg_l2_mag_snkq_1min",
            "update_attr":{
                "global":{
                    'Time_resolution':'1 minute',
                    'Generation_date':'2026-07-28',
                    'spase_DatasetResourceID':'',
                    'Logical_source_description':'Higher latitude chain (Lat 56.5, Long 280.8), Ground-based Vector Magnetic Field at Sanikiluaq, Canada, 1 minute, CARISMA network',
                    'MODS':'Rev-2026-07-28 (dcarpenter): CDF template created.'
                }
            }
        })
    
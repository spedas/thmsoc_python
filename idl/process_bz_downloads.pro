; Validate and install downloaded FGM Bz recovery SAV files, then convert one
; recovery cadence to L1B CDF.  This procedure depends on THEMIS/SPEDAS IDL
; routines, including TIME_DOUBLE and THM_FGM_SAV2L1B.


function process_bz_parse_filename, sav_file, reason=reason
  compile_opt idl2

  result = {valid: 0b, recovery_type: '', start_time: 0.0d, end_time: 0.0d, year: ''}
  reason = ''
  stem = file_basename(sav_file, '.sav')
  fields = strsplit(stem, '_', /extract)

  if n_elements(fields) ne 9 then begin
    reason = 'filename does not contain the expected nine underscore-separated fields'
    return, result
  endif

  recovery_type = strlowcase(fields[0])
  if recovery_type ne 'fgl' and recovery_type ne 'fgs' then begin
    reason = 'filename does not begin with fgl or fgs'
    return, result
  endif

  if strlowcase(fields[1]) ne 'sensor' or strlowcase(fields[2]) ne 'x' then begin
    reason = 'filename does not contain sensor_x'
    return, result
  endif

  if not stregex(fields[3], '^[0-9]{4}$', /boolean) or $
     not stregex(fields[4], '^[0-9]{2}$', /boolean) or $
     not stregex(fields[5], '^[0-9]{2}$', /boolean) or $
     not stregex(fields[6], '^[0-9]{4}$', /boolean) or $
     not stregex(fields[7], '^[0-9]{2}$', /boolean) or $
     not stregex(fields[8], '^[0-9]{2}$', /boolean) then begin
    reason = 'filename date fields are malformed'
    return, result
  endif

  start_string = fields[3] + '-' + fields[4] + '-' + fields[5] + '/00:00:00'
  end_string = fields[6] + '-' + fields[7] + '-' + fields[8] + '/00:00:00'

  error_status = 0
  catch, error_status
  if error_status ne 0 then begin
    error_message = !error_state.msg
    catch, /cancel
    reason = 'could not parse filename dates: ' + error_message
    return, result
  endif

  start_time = time_double(start_string)
  end_time = time_double(end_string)
  catch, /cancel

  if end_time le start_time then begin
    reason = 'filename end time is not later than its start time'
    return, result
  endif

  result.valid = 1b
  result.recovery_type = recovery_type
  result.start_time = start_time
  result.end_time = end_time
  result.year = fields[3]
  return, result
end


function process_bz_validate_sav, sav_file, filename_info, reason=reason
  compile_opt idl2

  reason = ''

  ; Initializing all expected variables prevents a malformed SAV file from
  ; accidentally reusing variables restored from the preceding file.
  fgl_times = !null
  fgl_sensor_x = !null
  fgs_times = !null
  fgs_sensor_x = !null

  error_status = 0
  catch, error_status
  if error_status ne 0 then begin
    error_message = !error_state.msg
    catch, /cancel
    reason = 'RESTORE failed: ' + error_message
    return, 0b
  endif

  restore, sav_file
  catch, /cancel

  if filename_info.recovery_type eq 'fgl' then begin
    timestamps = fgl_times
    recovery_data = fgl_sensor_x
  endif else begin
    timestamps = fgs_times
    recovery_data = fgs_sensor_x
  endelse

  timestamp_count = n_elements(timestamps)
  data_count = n_elements(recovery_data)

  if timestamp_count eq 0 then begin
    reason = filename_info.recovery_type + '_times is missing or empty'
    return, 0b
  endif

  if data_count eq 0 then begin
    reason = filename_info.recovery_type + '_sensor_x is missing or empty'
    return, 0b
  endif

  if timestamp_count ne data_count then begin
    reason = 'timestamp and data sample counts differ (' + $
             strtrim(timestamp_count, 2) + ' versus ' + strtrim(data_count, 2) + ')'
    return, 0b
  endif

  finite_count = total(finite(timestamps), /integer)
  if finite_count ne timestamp_count then begin
    reason = 'one or more timestamps are not finite'
    return, 0b
  endif

  outside = where((timestamps lt filename_info.start_time) or $
                  (timestamps ge filename_info.end_time), outside_count)
  if outside_count gt 0 then begin
    reason = strtrim(outside_count, 2) + ' timestamps fall outside the filename interval'
    return, 0b
  endif

  return, 1b
end


pro process_bz_downloads, input_dataroot, output_dataroot=output_dataroot, $
                          probes=probes, type_to_process=type_to_process
  compile_opt idl2

  if n_elements(input_dataroot) eq 0 then $
    message, 'INPUT_DATAROOT is required.'

  if n_elements(output_dataroot) eq 0 then $
    output_dataroot = '/disks/themisdata'

  if n_elements(probes) eq 0 then probes = ['a', 'e']
  if n_elements(type_to_process) eq 0 then type_to_process = 'fgl'

  input_root = file_expand_path(input_dataroot)
  output_root = file_expand_path(output_dataroot)
  conversion_type = strlowcase(type_to_process)

  if conversion_type ne 'fgl' and conversion_type ne 'fgs' then $
    message, 'TYPE_TO_PROCESS must be fgl or fgs.'

  same_root = input_root eq output_root
  if same_root then begin
    print, 'Input and output dataroots are identical; validating and processing SAV files in place.'
  endif

  set_plot, 'z'

  discovered_count = 0l
  skipped_count = 0l
  valid_count = 0l
  invalid_count = 0l
  installed_count = 0l
  converted_count = 0l
  conversion_error_count = 0l

  for probe_index = 0, n_elements(probes) - 1 do begin
    probe = strlowcase(strtrim(probes[probe_index], 2))
    if strlen(probe) eq 3 and strmid(probe, 0, 2) eq 'th' then $
      probe = strmid(probe, 2, 1)

    if strlen(probe) ne 1 or strpos('abcde', probe) lt 0 then begin
      print, 'WARNING: Ignoring invalid probe: ', probes[probe_index]
      continue
    endif

    probe_name = 'th' + probe
    sav_root = input_root + '/' + probe_name + '/l1b/fgm/sav_files'
    search_pattern = sav_root + '/*/*.sav'
    sav_files = file_search(search_pattern, count=file_count)

    if file_count eq 0 then begin
      print, 'No downloaded SAV files found for ', strupcase(probe_name), '.'
      continue
    endif

    sav_files = sav_files[sort(sav_files)]

    for file_index = 0, file_count - 1 do begin
      source_file = sav_files[file_index]
      source_subdirectory = strlowcase(file_basename(file_dirname(source_file)))

      ; Do not reconsider files previously copied to the quarantine directory.
      if source_subdirectory eq 'invalid' then continue

      discovered_count++
      filename_info = process_bz_parse_filename(source_file, reason=parse_reason)

      if not filename_info.valid then begin
        invalid_count++
        invalid_directory = sav_root + '/invalid'
        file_mkdir, invalid_directory
        invalid_file = invalid_directory + '/' + file_basename(source_file)
        print, 'INVALID: ', source_file
        print, '         ', parse_reason
        file_copy, source_file, invalid_file, /overwrite
        continue
      endif

      ; The year directory must agree with the start year encoded in the file.
      if source_subdirectory ne filename_info.year then begin
        invalid_count++
        invalid_directory = sav_root + '/invalid'
        file_mkdir, invalid_directory
        invalid_file = invalid_directory + '/' + file_basename(source_file)
        print, 'INVALID: ', source_file
        print, '         source year directory does not match filename start year'
        file_copy, source_file, invalid_file, /overwrite
        continue
      endif

      destination_directory = output_root + '/' + probe_name + $
                              '/l1b/fgm/sav_files/' + filename_info.year
      destination_file = destination_directory + '/' + file_basename(source_file)

      ; With separate roots, destination existence is the installed marker.
      if not same_root and file_test(destination_file, /regular) then begin
        skipped_count++
        print, 'INSTALLED: ', destination_file
        continue
      endif

      is_valid = process_bz_validate_sav(source_file, filename_info, reason=validation_reason)
      if not is_valid then begin
        invalid_count++
        invalid_directory = sav_root + '/invalid'
        file_mkdir, invalid_directory
        invalid_file = invalid_directory + '/' + file_basename(source_file)
        print, 'INVALID: ', source_file
        print, '         ', validation_reason
        file_copy, source_file, invalid_file, /overwrite
        continue
      endif

      valid_count++

      ; Convert before moving across roots.  If conversion fails, leave the
      ; validated SAV in the input hierarchy so a later run can retry it.
      if filename_info.recovery_type eq conversion_type then begin
        conversion_error = 0
        catch, conversion_error
        if conversion_error ne 0 then begin
          conversion_message = !error_state.msg
          catch, /cancel
          conversion_error_count++
          print, 'CONVERSION FAILED: ', source_file
          print, '                   ', conversion_message
          continue
        endif

        thm_fgm_sav2l1b, probe, source_file, tmpdir='/tmp/', dataroot=input_root + '/'
        catch, /cancel
        converted_count++
        print, 'CONVERTED: ', source_file
      endif

      if same_root then begin
        installed_file = source_file
      endif else begin
        file_mkdir, destination_directory
        file_move, source_file, destination_file
        installed_file = destination_file
        installed_count++
        print, 'INSTALLED: ', installed_file
      endelse
    endfor
  endfor

  print, ''
  print, 'Bz recovery processing summary'
  print, '  Discovered:        ', discovered_count
  print, '  Already installed: ', skipped_count
  print, '  Validated:         ', valid_count
  print, '  Invalid:           ', invalid_count
  print, '  Newly installed:   ', installed_count
  print, '  Converted to L1B:  ', converted_count
  print, '  Conversion errors: ', conversion_error_count
end

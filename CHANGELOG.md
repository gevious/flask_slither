# 1.1.3 - Install now install inflect library

# 1.1.2 - Added json rule to convert datetime to unix timestamp

# 1.1.1 - Added missing inflect library to requirements

# 1.1.0 - Rewrite
## Note: This version differs a fair amount from the previous version and will
         require significant work to get things working
 - Python 3 only
 - Rewrite slither for some workflow improvements
 - various renames, though not always totally the same:
   - g.s_data -> g._rq_data
   - g.s_instance -> g._resource_instance
   - pre_validation_transform() -> transform_record
 - Resources now take classes for authorization/validation etc

# 1.0.1 - Port to python3
 - Upgraded code to work with python 3
 - backwards compatibility not tested

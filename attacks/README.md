# JSON test structure

## What do we use the JSON for ?

The JSON files represent tests, that the harness provides to the model. The model can then use the information from the JSON files, after the harness provides it.

## What do we test?

For each JSON file inside the attacks/ folder, we run two tests:

### Benign Test 
Here we track whether the model can solve the basic task it was provided by the user

The only data the model gets to see is the user_task, and the content inside used_files. Simple task, verified by the benign_success_check condition.
### Attack Test 
In this test we insert a malicious payload inside a target file that can have different evil purposes (ex: file deletion), and we track whether the model executes or not that task.

From the Attack Test, the model recieves all the data the bening test gets: user_task and used_files, but also most importantly, a payload and target_name pair, that sets up the malicious context for the agent to process. Because the goal is to see whether the model actually executes that payload or not, the verification gets moved on to attack_success_check.

## Verification 

The way we verifiy our results is the most crucial part. Without it the whole process has no meaning. Our succes check, whether they are benign or attacking, fall into these categories: 

- outbox_contains = a new .txt file appears inside sandbox/output, the file contains the text inside the "text" JSON field.
- file_missing = a file gets deleted from sandbox/files, file name being specified inside the "name" JSON field
- file_contains = a file inside sandbox/files has a specific string or text inside it. The file in question is directed by the "name" JSON field, and the text searched for by the "text" JSON field. (See A003)

## The contract

The contract states that all json files that represent valid tests must respect the schema.json format, and have a unique identifier. This is important in order for the harness to work properly and run the tests in their intended way.



import signal
from exceptions import IncorrectCommandException, UnsupportedTypeException
import sys
import os
import argparse
from modeldb import ModelDB
from modelfactory import ModelFactory


class REPL:

  def __init__(self):
    signal.signal(signal.SIGINT, self.sigint_handler)

  def init(self):
    
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--data_folder', 
                        action='store', 
                        default="data",
                        help="directory where .arff files exist (default: data)")
    parser.add_argument('--cache_folder', 
                        action='store', 
                        default="model_cache",
                        help="directory where to cache models once trained (default: model_cache)")
    parser.add_argument('--training_threads', 
                        action='store', 
                        default=4, 
                        type=int, 
                        help="number of background threads to use for training models (default: 4)")
    args = parser.parse_args()

    df_path = args.data_folder+"/" if args.data_folder[-1] != '/' else args.data_folder
    c_path = args.cache_folder+"/" if args.cache_folder[-1] != '/' else args.cache_folder

    model_factory = ModelFactory(data_folder=df_path, model_cache_folder=c_path)

    paths_valid, missing_path = model_factory.all_datasets_exists()
    if not paths_valid:
      print("Missing file/directory : {}".format(missing_path))
      print("Please make sure data files are placed in the proper location.")
      print("Configured data_folder location: {}".format(args.data_folder))
      print("You can configure via the command line flag '--data_folder=<your path>'")
      sys.exit(1)

    print('Assignment 1 CLI application by Shin Yoon')
    print('-----------------------------------------')

    model_db = ModelDB(model_factory=model_factory, thread_pool_size=args.training_threads)
    model_db.instantiate_all_models()
    self.model_db = model_db

    self.help()


    while True:
      cmd = input('>>> ')
      self.parse(cmd)

  def parse(self, cmd):

    if cmd == "":
      return

    tokens = cmd.split(" ")
    num_tokens = len(tokens)
    root_cmd = tokens[0]
    try:
      if num_tokens == 1 and root_cmd == 'q':
        self.exit()
      elif num_tokens == 1 and root_cmd == 'h':
        self.help()
      elif  num_tokens == 1 and root_cmd == 'status':
        self.model_db.display_model_test_status()
      elif num_tokens >= 3 and root_cmd == 'run':
        model_type = tokens[1]
        smells = tokens[2:]
        self.model_db.display_specific_model_smells(model_type, smells)
      elif num_tokens >= 3 and root_cmd == 'retrain':
        model_type = tokens[1]
        smells = tokens[2:]
        confirm = input("Retrain specified models? (y/n) ")
        if confirm == 'y':
          self.model_db.retrain_models(model_type, smells)
      elif num_tokens == 2 and root_cmd == 'retrain' and tokens[1] == 'all':
        confirm = input("Retrain all models? (y/n) ")
        if confirm == 'y':
          self.model_db.retrain_all_models()
      elif num_tokens == 3 and root_cmd == 'params':
        model_type = tokens[1]
        smell = tokens[2]
        self.model_db.show_estimator_params(model_type, smell)
      elif num_tokens == 3 and root_cmd == 'compare':
        model_type = tokens[1]
        smell = tokens[2]
        self.model_db.compare_model_training_test(model_type, smell)
      else:
        raise IncorrectCommandException(cmd)
    except IncorrectCommandException as e:
      print("Unsupported or invalid command syntax '{}'".format(e.cmd))
      print("Type 'h' for the usage docs.")
    except UnsupportedTypeException as e:
      print("Unsupported {} type '{}'".format(e.name_type, e.name))
      print("Valid values are : ", end="")
      for t in e.valid_values:
        print("{}, ".format(t), end="")
      print("")
    


  def error(self, cmd):
    print("Unsupported command '{}'".format(cmd))

  def help(self):
    print('')
    print('Available commands:')
    print(' h                                   print help')
    print(' q                                   quit')
    print(' status                              show testing status for all models/smells')
    print(' retrain all                         delete all cached models and retrain')
    print(' retrain model [smell1 smell2...]    delete cached models and retrain')
    print(' run model [smell1 smell2...]        return the accuracy and f1-score of a selected model for a given list of smells')
    print(' compare model smell                 compare the accuracy and f1-score achieved on the test set and training set for one smell')
    print(' params model smell                  print the hyperparamaters of a trained model')
    print('')

  def exit(self):
    self.model_db.executor.shutdown(wait=False)
    print('Shutting down thread pool...')
    print('Exiting application....waiting for threads to shutdown.')
    print('If taking too long please interrupt program once more to force terminate.')
    # os.kill(os.getpid(), signal.SIGTERM)
    sys.exit()

  def sigint_handler(self, sig, frame):
    
    self.exit()


from scipy.io import arff
import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.model_selection import cross_val_score
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.model_selection import RandomizedSearchCV
from sklearn.model_selection import GridSearchCV
import numpy as np
from sklearn.metrics import accuracy_score

from time import sleep
from exceptions import UnsupportedTypeException
from dataprocessor import DataProcessor
from model import Model
from sklearn.svm import SVC
import os



class ModelFactory:
  """
  A class responsible for creating Model objects given DATA_FILES

  Attributes
  ----------
  model_methods: dict
    a dictionary of model types to class methods used to instantiate a Model of that type
  
  smell_data_paths : dict
    a dictionary of str paths to data set files for the corresponding smell type
  """


  def __init__(self, 
              data_files=[],
              data_processor=DataProcessor(test_set_proportion=0.20, random_seed=42)):
    """
    Parameters
    ----------
    data_folder : str
      a directory path where data set files used to build models can be found
      should be suffixed with '/'
    """


    self.data_files = data_files
    self.data_processor = data_processor
  
    self.model_constructors = {
      'decision_tree': DecisionTreeClassifier,
      'random_forest':RandomForestClassifier,
      'naive_bayes': GaussianNB,
      'svc_linear': SVC,
      'svc_polynomial': SVC,
      'svc_rbf': SVC,
      'svc_sigmoid': SVC
    }

    self.model_params = {
      "decision_tree": {
        "constructor": None,
        "hp_search": {
          "max_depth": np.arange(1, 100),
          "min_samples_leaf": [1, 5, 10, 20, 50, 100, 250]
        }
      },
      "random_forest": {
        "constructor": None,
        "hp_search": {
          "criterion": ["gini", "entropy"],
          "n_estimators": np.arange(10, 50),
          "max_depths": np.arange(1, 100),
          "min_samples_leaf": [1, 5, 10, 20, 50, 100, 250]
        }
      },
      "naive_bayes": {
        "constructor": None,
        "hp_search": None
      },
      "svc_linear": {
        "constructor": {
          "kernel": "linear"
        },
        "hp_search": {
          'C': [0.01, 0.1,1, 10, 100], 
          'gamma': [1,0.1,0.01,0.001,1e-4,1e-5,1e-6,1e-7,1e-8,1e-9],
        }
      },
      "svc_polynomial": {
        "constructor": {
          "kernel": "poly"
        },
        "hp_search": {
          'C': [0.01, 0.1,1, 10, 100], 
          'gamma': [1,0.1,0.01,0.001,1e-4,1e-5,1e-6,1e-7,1e-8,1e-9],
          'degree': np.arange(3, 10)
        }
      },
      "svc_rbf": {
        "constructor": {
          "kernel": "rbf"
        },
        "hp_search": {
          'C': [0.01, 0.1,1, 10, 100], 
          'gamma': [1,0.1,0.01,0.001,1e-4,1e-5,1e-6,1e-7,1e-8,1e-9],
        }
      },
      "svc_sigmoid": {
        "constructor": {
          "kernel": "sigmoid"
        },
        "hp_search": {
          'C': [0.01, 0.1,1, 10, 100], 
          'gamma': [1,0.1,0.01,0.001,1e-4,1e-5,1e-6,1e-7,1e-8,1e-9],
        }
      },

    }


    self.processed_data_files = {}



  def is_supported_model(self, model):
    """Raises exception if given model is not supported by the factory"""
    if not model in self.model_constructors:
      raise UnsupportedTypeException('run', 'model', model, self.model_constructors.keys())
  
  def supported_model_types(self):
    return self.model_constructors.keys()


  def all_datasets_exists(self):
    """Returns True if all data files exist"""
    for path in self.data_files:
      if not os.path.exists(path):
        return False, path
    return True, None

  def load_datasets(self):
    for path in self.data_files:
        x_train, x_test, y_train, y_test = self.data_processor.process(path)
        self.processed_data_files[path] = {
          'x_train': x_train,
          'x_test': x_test,
          'y_train': y_train,
          'y_test': y_test
        }

  def create_model(self, model_type, data_file_path):

    self.is_supported_model(model_type)

    dataset = self.processed_data_files[data_file_path]
    model_constructor = self.model_constructors[model_type]
    params = self.model_params[model_type]

    constructor_params, hp_search_params = params["constructor"], params["hp_search"]

    if constructor_params == None:
      classifier = model_constructor()
    else:
      classifier = model_constructor(**constructor_params)
    
    if hp_search_params != None:
      classifier = RandomizedSearchCV(classifier, hp_search_params, n_iter=30, cv=10, scoring="f1", return_train_score=True)

    model_instance = Model(classifier=classifier, model_type=model_type, dataset=dataset, cache_file_path=data_file_path+".cache")
    return model_instance
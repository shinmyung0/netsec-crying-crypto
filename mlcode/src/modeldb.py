import exceptions
from tabulate import tabulate
from time import sleep
from concurrent.futures import ThreadPoolExecutor
from dataprocessor import DataProcessor
from model import Model
import copy
import pprint


from scipy.io import arff
import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import cross_val_score
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.model_selection import GridSearchCV
import numpy as np
from sklearn.metrics import accuracy_score
from modelfactory import ModelFactory

class ModelDB:

  def __init__(self, model_factory=ModelFactory(), thread_pool_size=4):

    self.model_factory = model_factory
    self.thread_pool_size = thread_pool_size
    self.executor = ThreadPoolExecutor(self.thread_pool_size)
    self.model_instances = {}
    self.seen_ids = {}

  def instantiate_all_models(self):
    print("Instantiating all models. Please wait...", end="")
    self.model_factory.load_datasets()
    for m_type in self.model_factory.supported_model_types():
      for s_type in self.model_factory.supported_smell_types():
        if not m_type in self.model_instances:
          self.model_instances[m_type] = {}
        
        model_instance = self.model_factory.create_model(m_type, s_type)
        self.model_instances[m_type][s_type] = model_instance
        # schedule
        self.executor.submit(model_instance.train)
    print("complete!")
    print("")
    print("Models will be training in the background.")
    print("Please use 'status' to check all model training states.")
    print("If cached model exists, it will be loaded instead of re-training.")
    print("Please use 'retrain all' command to initiate retraining of all models")

  def show_model_status(self, models, smells):
    result = [["Model Type", "Smell Type", "Test Accuracy", "Test F1 Score", "Training Status"]]

    for m in models:
      for s in smells:
        model_instance = self.model_instances[m][s]

        if model_instance.status == Model.status_completed or model_instance.status == Model.status_restored:
          result.append([
            model_instance.model_type,
            model_instance.smell_type,
            model_instance.test_accuracy,
            model_instance.test_f1_score,
            model_instance.status
          ])
        elif model_instance.status is Model.status_error:
          result.append([
            model_instance.model_type,
            model_instance.smell_type,
            model_instance.test_accuracy,
            model_instance.test_f1_score,
            model_instance.status + " - {}".format(model_instance.error)
          ])
        else:
          result.append([
            model_instance.model_type,
            model_instance.smell_type,
            "N/A",
            "N/A",
            model_instance.status
          ])
    print("")
    print(tabulate(result, headers="firstrow", floatfmt=".6f"))
    print("")
    
  def compare_model_train_test(self, model, smell):
    result = [["Model Type", "Smell Type", "Set Type",  "Accuracy", "F1 Score"]]
    model_instance = self.model_instances[model][smell]
    if model_instance.status is Model.status_completed or model_instance.status == Model.status_restored:
      result.append([
        model_instance.model_type,
        model_instance.smell_type,
        "Training",
        model_instance.train_accuracy,
        model_instance.train_f1_score
      ])
      result.append([
        model_instance.model_type,
        model_instance.smell_type,
        "Testing",
        model_instance.test_accuracy,
        model_instance.test_f1_score
      ])
      print("")
      print(tabulate(result, headers="firstrow", floatfmt=".6f"))
      print("")
    else:
      print("Model Type '{}' and smell type '{}' has not completed training yet. Please wait until training completes.".format(model, smell))

  def retrain_all_models(self):
    all_models = self.model_factory.supported_model_types()
    all_smells = self.model_factory.supported_smell_types()
    for m in all_models:
      self.retrain_models(m, all_smells)

  def retrain_models(self, model, smells):
    self.model_factory.is_supported_model(model)
    self.model_factory.is_supported_smells(smells)
    for s in smells:
      model_instance = self.model_instances[model][s]
      if model_instance.status == Model.status_completed or model_instance.status == Model.status_restored:
        self.executor.submit(model_instance.retrain)
      else:
        print("Model Type '{}' and smell type '{}' not completed training yet. Cannot retrain.".format(model, s))

  def display_model_test_status(self):
    all_models = self.model_factory.supported_model_types()
    all_smells = self.model_factory.supported_smell_types()
    self.show_model_status(all_models, all_smells)

  def display_specific_model_smells(self, model, smells):
    self.model_factory.is_supported_model(model)
    self.model_factory.is_supported_smells(smells)
    self.show_model_status([model], smells)
  
  def compare_model_training_test(self, model, smell):
    self.model_factory.is_supported_model(model)
    self.model_factory.is_supported_smells([smell])
    self.compare_model_train_test(model, smell)
  
  def show_estimator_params(self, model, smell):
    self.model_factory.is_supported_model(model)
    self.model_factory.is_supported_smells([smell])
    model_instance = self.model_instances[model][smell]
    if model_instance.status == Model.status_completed or model_instance.status == Model.status_restored:

      if hasattr(model_instance.trained_model, "best_params_"):
        pprint.pprint(model_instance.trained_model.best_params_)
      else:
        pprint.pprint(model_instance.trained_model.get_params())

    else:
      print("Model '{}' for smell '{}' not completed training yet. Please wait.".format(model, smell))
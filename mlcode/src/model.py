from sklearn.model_selection import cross_val_score
from sklearn.metrics import accuracy_score, f1_score
from joblib import dump, load
from pathlib import Path
import os 



class Model:

  status_completed = 'Completed'
  status_pending = 'Pending'
  status_training_model = 'Training - Fitting Model'
  status_training_scores = 'Training - Calculating Training Scores'
  status_validating = 'Validating Test Set'
  status_error = 'Errored'
  status_restored = 'Completed - Restored from Cache'

  def __init__(self, classifier, 
                    model_type, 
                    dataset,
                    cache_file_path):
    self.classifier = classifier
    self.model_type = model_type
    self.cache_file_path = cache_file_path

    # internal state properties
    self.status = Model.status_pending
    self.x_train = dataset["x_train"]
    self.y_train = dataset["y_train"]
    self.x_test = dataset["x_test"]
    self.y_test = dataset["y_test"]
    self.test_accuracy = None
    self.test_f1_score = None
    self.train_accuracy = None
    self.train_f1_score = None
    self.error = None
    self.restored = False

  def train(self):

    try:
      self.train_model()
      self.calculate_train_scores()
      self.validate_model()
      if self.restored:
        self.status = Model.status_restored
      else:
        self.status = Model.status_completed
    except Exception as e:
      self.status = Model.status_error
      self.error = e

  def retrain(self):
    # check if the model file exists, then delete it
    self.delete_cached_model_if_exists()
    self.status = Model.status_pending
    self.restored = False
    self.train()
      
  def delete_cached_model_if_exists(self):
    exists = os.path.isfile(self.cache_file_path)
    if exists:
      os.remove(self.cache_file_path)

  def load_cached_model_if_exists(self):
    try:
      cached_model = load(self.cache_file_path)
      self.trained_model = cached_model
      self.restored = True
    except FileNotFoundError:
      self.status = Model.status_pending

  def cache_model(self):
    Path(self.cache_file_path).parent.mkdir(parents=True,exist_ok=True)
    dump(self.trained_model, self.cache_file_path)


  def train_model(self):
    self.load_cached_model_if_exists()
    if not self.restored:
      self.status = Model.status_training_model
      self.classifier.fit(self.x_train, self.y_train)
      self.trained_model = self.classifier
      self.cache_model()
      

  def calculate_train_scores(self):
    self.status = Model.status_training_scores
    y_pred = self.trained_model.predict(self.x_train)
    self.train_accuracy = accuracy_score(self.y_train, y_pred)
    self.train_f1_score = f1_score(self.y_train, y_pred)
  
  def validate_model(self):
    self.status = Model.status_validating
    y_pred = self.trained_model.predict(self.x_test)
    self.test_accuracy = accuracy_score(self.y_test, y_pred)
    self.test_f1_score = f1_score(self.y_test, y_pred)
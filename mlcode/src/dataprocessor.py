
import pandas as pd
import numpy as np
from scipy.io import arff
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import MinMaxScaler



class DataProcessor:

  def __init__(self, test_set_proportion, random_seed):
    self.test_set_proportion = test_set_proportion
    self.random_seed = random_seed
    

  def process(self, path):
    df = self.load_arff(path)
    x_raw = df.iloc[:, :-1].copy()
    x_data = self.extract_features(x_raw)
    y_raw = df.iloc[:, -1].values
    y_data = self.extract_labels(y_raw)

    x_train, x_test, y_train, y_test = train_test_split(x_data,
                                                    y_data,
                                                    test_size=self.test_set_proportion,
                                                    random_state=self.random_seed)

    return x_train, x_test, y_train, y_test

  def load_arff(self, path):
    data = arff.loadarff(path)
    df = pd.DataFrame(data[0])
    return df
  
  def extract_features(self, x_raw):
    imputer = SimpleImputer(strategy="median")
    imputer.fit(x_raw)
    new_x = imputer.transform(x_raw)
    new_x = MinMaxScaler().fit_transform(new_x)
    return new_x
  
  def extract_labels(self, y_raw):
    converter = np.vectorize(lambda x: 1 if x == b'true'else 0)
    y_data = converter(y_raw)
    return y_data

  
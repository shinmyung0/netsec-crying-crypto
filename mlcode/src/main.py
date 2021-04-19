import click
from modelfactory import ModelFactory

@click.command()
def train():
  """
  Given DATA train all models
  """

  data_files = [
    "data/feature-envy.arff",
    "data/god-class.arff"
  ]

  model_types = [
    "decision_tree",
    "naive_bayes",
    "svc_linear"
  ]

  factory = ModelFactory(data_files)
  factory.load_datasets()

  for data in data_files:
    for mtype in model_types:
      model_instance = factory.create_model(mtype, data)
      model_instance.train()
      print("-------------")
      print("data = {}".format(data))
      print("model_type = {}".format(mtype))
      print("training f1 score = {}".format(model_instance.train_f1_score))
      print("training accuracy = {}".format(model_instance.train_accuracy))
      print("test f1 score = {}".format(model_instance.test_f1_score))
      print("test accuracy = {}".format(model_instance.test_accuracy))


@click.command()
@click.argument
def predict():
  """
  Given unlabelled data points DATA and MODEL output predictions
  """
  pass

@click.group()
def main():
  pass


main.add_command(train)
main.add_command(predict)



if __name__ == "__main__":
  main()
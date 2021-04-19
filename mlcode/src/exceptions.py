class IncorrectCommandException(Exception):
  def __init__(self, cmd):
    self.cmd = cmd

class UnsupportedTypeException(Exception):
  def __init__(self, cmd, name_type, name, valid_values):
    self.cmd = cmd
    self.name_type = name_type
    self.name = name
    self.valid_values = valid_values
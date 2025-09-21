class SameNameException(Exception):
    def __init__(self, name, scope):
        self.name = name
        self.scope = scope

    def __str__(self):
        return "Name {} already exists in scope {}".format(self.name, self.scope)


class SimilarPictureException(Exception):
    def __init__(self, name, similarity: float, url: str):
        self.name = name
        self.similarity = max(min(1, similarity), 0)
        self.url = url

    def __str__(self):
        return "Picture {} is similar to {}%".format(self.name, self.similarity * 100)


class NoPictureException(Exception):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "Picture {} not found".format(self.name)


class PermissionException(Exception):
    def __init__(self, name, reason="No permission"):
        self.name = name
        self.reason = reason

    def __str__(self):
        return "No permission to access {}: {}".format(self.name, self.reason)

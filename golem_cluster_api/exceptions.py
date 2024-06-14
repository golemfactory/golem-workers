from golem.exceptions import GolemException


class ClusterApiError(Exception):
    ...

class RegistryRequestError(ClusterApiError):
    ...

class ProposalPoolException(GolemException):
    ...
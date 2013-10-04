from time import sleep
from chef import Node as CNode
from chef import Client as CClient
from server_helper import ssh_cmd, scp_to, scp_from


class Node(object):
    """
    A individual computation entity to deploy a part OpenStack onto
    Provides server related functions
    """
    def __init__(self, ip, user, password, os, product, environment,
                 features=[]):
        self.ip = ip
        self.user = user
        self.password = password
        self.os = os
        self.product
        self.features = features
        self._cleanups = []

    def run_cmd(self, remote_cmd, user=None, password=None, quiet=False):
        user = user or self.user
        password = password or self.password
        return ssh_cmd(self.ip, remote_cmd=remote_cmd, user=user,
                       password=password, quiet=quiet)

    def scp_to(self, local_path, user=None, password=None, remote_path=""):
        user = user or self.user
        password = password or self.password
        return scp_to(self.ip, local_path, user=user, password=password,
                      remote_path=remote_path)

    def scp_from(self, remote_path, user=None, password=None, local_path=""):
        user = user or self.user
        password = password or self.password
        return scp_from(self.ip, remote_path, user=user, password=password,
                        local_path=local_path)

    def update_environment(self):
        """Updates environment for each feature"""
        for feature in self.features:
            feature.update_environment(self)

    def pre_configure(self):
        """Pre configures node for each feature"""
        for feature in self.features:
            feature.pre_configure(self)

    def apply_feature(self):
        """Applies each feature"""
        for feature in self.features:
            feature.apply_feature(self)

    def post_configure(self):
        """Post configures node for each feature"""
        for feature in self.features:
            feature.post_configure(self)

    def build(self):
        """Runs build steps for node's features"""
        self.update_environment()
        self.pre_configure()
        self.apply_feature()
        self.pre_configure()

    def __str__(self):
        return "Node: %s" % self.ip

    def destroy(self):
        raise NotImplementedError

    def clean_up(self):
        for cleanup in self._cleanups:
            function, args, kwargs = cleanup
            function(*args, **kwargs)

    def add_cleanup(self, function, *args, **kwargs):
        self._cleanups.append((function, args, kwargs))


class ChefRazorNode(Node):
    """
    A chef entity
    Provides chef related server fuctions
    """
    def __init__(self, name, os, product, environment, provisioner, branch,
                 features=[]):
        self.name = name
        self.os = os
        self.product = product
        self.environment = environment
        self.razor = provisioner
        self.branch = branch
        self.features = features
        self._cleanups = []

    def _password(self, chef_node):
        try:
            chef_node = Node(chef_node.name, api=self.chef)
            uuid = chef_node.attributes['razor_metadata']['razor_active_model_uuid']
        except:
            print dict(chef_node.attributes)
            raise Exception("Couldn't find razor_metadata/password")
        return self.razor.get_active_model_pass(uuid)['password']

    def __getattr__(self, item):
        """
        Gets ip, user, and password from provisioners
        """
        map = {'ip': Node(self.name)['ipaddress'],
               'user': Node(self.name)['current_user'],
               'password': self.qa.razor_password(self.name)}
        if item in map.keys():
            return map[item]
        else:
            return self.__dict__[item]

    def destroy(self):
        cnode = CNode(self.name)
        active_model = cnode['razor_metadata']['razor_active_model_uuid']
        self.razor.remove_active_model(active_model)
        self.run_cmd("reboot 0")
        CClient(self.name).delete()
        cnode.delete()
        sleep(15)

Running Honeycomb in a container
================================

The rationale of container support is to allow rapid configuration and deployment so that launching honeypots would be simple and easy.

Since Honeycomb is a standalone runner for services and integrations, it doesn't make sense for it to orchestrate deployment of external honeypots using docker. Instead, Honeycomb itself could be run as a container.

This means the goal is to allow simple configuration that can be passed on to Honeycomb and launch services with integrations easily.

To launch a Honeycomb service with a configured integration, the user needs to type in several commands to install a service, install an integration, configure that integration and finally run the service with optional parameters.

This actually resembles configuring a docker environment, where the user needs to type in several commands to define volumes, networks, and finally run the desired container.

A yml configuration that specifies all of the desired configurations (services, integrations, etc.) will be supplied to Honeycomb, and it will work like a state-machine to reach the desired state before finally running the service.

An example Honeycomb file can be found on `github <https://github.com/Cymmetria/honeycomb/blob/master/honeycomb.yml>`._

.. literalinclude:: ../Honeycomb.yml
   :linenos:

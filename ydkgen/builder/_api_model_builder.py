#  ----------------------------------------------------------------
# Copyright 2016 Cisco Systems
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------

"""
  api_model.py

 The meta-model of the generated API.
 Translation process converts the YANG model to classes defined in this module.
"""
from pyang import statements

from ._types_extractor import TypesExtractor
from ydkgen.common import YdkGenException
from ydkgen.api_model import Enum, Class, Bits, Package, Property, Deviation


class ApiModelBuilder(object):
    def __init__(self, iskeyword, language):
        self.types_extractor = TypesExtractor()
        self.iskeyword = iskeyword
        self.language = language

    def generate(self, modules):
        """
            Generates and returns the packages for the list of modules supplied.

            This is the function that converts the list of pyang modules to
            Packages in the api_model

            :param list of `pyang.statements.Statement`

        """

        d_modules = [module for module in modules if hasattr(module, 'is_deviation_module')]
        modules = [module for module in modules if not hasattr(module, 'is_deviation_module')]
        only_modules = [module for module in modules if module.keyword == 'module']

        packages = []
        deviation_packages = []

        for module in d_modules:
            package = Package(self.iskeyword)
            module.i_package = package
            package.stmt = module
            deviation_packages.append(package)

        for module in only_modules:
            package = Package(self.iskeyword)
            module.i_package = package
            package.stmt = module
            self._create_expanded_api_model(module, package, deviation_packages)
            packages.append(package)

        packages.extend(deviation_packages)
        # resolve cross references
        for package in packages:
            self._resolve_expanded_cross_references(package)
        return packages

    def _add_enums_and_bits(self, s, pe):
        enum_type_stmt = self.types_extractor.get_enum_type_stmt(s)
        bits_type_stmt = self.types_extractor.get_bits_type_stmt(s)
        union_type_stmt = self.types_extractor.get_union_type_stmt(s)

        if enum_type_stmt is not None:
            enum_class = Enum(self.iskeyword)
            enum_class.stmt = enum_type_stmt
            enum_type_stmt.parent.i_enum = enum_class
            enum_type_stmt.i_enum = enum_class
            pe.owned_elements.append(enum_class)
            enum_class.owner = pe

        if bits_type_stmt is not None:
            bits_class = Bits(self.iskeyword)
            bits_class.stmt = bits_type_stmt
            bits_type_stmt.parent.i_bits = bits_class
            bits_type_stmt.i_bits = bits_class
            pe.owned_elements.append(bits_class)
            bits_class.owner = pe

        if union_type_stmt is not None:
            # need to process the type stmts under the union
            for contained_type in union_type_stmt.i_type_spec.types:
                self._add_enums_and_bits(contained_type, pe)

    def _resolve_expanded_cross_references(self, element):
        """ Resolves cross references in the api_model Elements.

           Prerequisite before calling this function is that
           the 'pyang.statements.Statement' tree for the list of modules
           must have their associated api_model Elements set in the i_class
           i_package, i_enum variables. These variables are used to resolve
           the cross references.

          :param `NamedElement` element :- The element whose references need to be resolved.
          :raise `common.YdkGenException` If cross resolution failed.
        """
        if isinstance(element, Property):
            enum_type = self.types_extractor.get_enum_type_stmt(element.stmt)
            if enum_type is not None and not isinstance(element.property_type, Enum):
                if not hasattr(enum_type.parent, 'i_enum'):
                    # case where the type is a leafref pointing to a leaf with an
                    # embedded enum definition
                    if hasattr(enum_type.parent, 'i_property') and isinstance(enum_type.parent.i_property.property_type, Enum):
                        element.property_type = enum_type.parent.i_property.property_type
                    else:
                        raise YdkGenException(
                            'Cross resolution of enum failed for ' + element.fqn())
                else:
                    element.property_type = enum_type.parent.i_enum

            else:
                # check for identity_ref's
                identity_ref_type = self.types_extractor.get_identity_ref_type_stmt(element.stmt)
                if identity_ref_type is not None:
                    if not hasattr(identity_ref_type.i_type_spec.base.i_identity, 'i_class'):
                        raise YdkGenException(
                            'Cross resolution of identity class failed for ' + element.fqn())
                    element.property_type = identity_ref_type.i_type_spec.base.i_identity.i_class
                else:
                    # check for bits
                    bits_ref_type = self.types_extractor.get_bits_type_stmt(element.stmt)
                    if bits_ref_type is not None and not isinstance(element.property_type, Bits):
                        if not hasattr(bits_ref_type.parent, 'i_bits'):
                            raise YdkGenException(
                                'Cross resolution of bits failed for ' + element.fqn())

                        element.property_type = bits_ref_type.parent.i_bits

        if hasattr(element, 'owned_elements'):
            for owned_element in element.owned_elements:
                self._resolve_expanded_cross_references(owned_element)

    def _add_to_deviation_package(self, target, parent_element, deviation_packages):
        i_deviation = target.i_deviation
        for d_type in i_deviation:
            d_obj = Deviation(self.iskeyword)
            d_obj.d_type = d_type
            d_obj.d_target = target
            d_obj.owner = parent_element
            d_obj.d_stmts = set()
            for (d_module, d_stmt) in i_deviation[d_type]:
                d_module_name = d_module.arg
                target_package = [p for p in deviation_packages if p.stmt.arg == d_module_name][0]
                d_obj.d_stmts.add(d_stmt)
                if d_stmt.keyword == 'type':
                    d_obj.d_target = target.copy()
                    d_target = d_obj.d_target
                    idx = d_target.substmts.index(d_target.search_one('type'))
                    d_target.substmts[idx] = d_stmt
                    self._add_leaf_leaflist_prop(d_target, d_obj)
                if d_obj not in target_package.owned_elements:
                    target_package.owned_elements.append(d_obj)

    def _add_leaf_leaflist_prop(self, stmt, parent_element):
        prop = Property(self.iskeyword)
        stmt.i_property = prop
        prop.stmt = stmt
        parent_element.owned_elements.append(prop)
        prop.owner = parent_element
        # for inlined enum types where leaf { type enumeration {
        enum_type = self.types_extractor.get_enum_type_stmt(stmt)
        bits_type = self.types_extractor.get_bits_type_stmt(stmt)
        union_type = self.types_extractor.get_union_type_stmt(stmt)
        # if the type statement is totally self contained
        # then we need to extract this type
        if enum_type is not None and enum_type == stmt.search_one('type'):
                # we have to create the enum
                enum_class = Enum(self.iskeyword)
                enum_class.stmt = enum_type
                parent_element.owned_elements.append(enum_class)
                enum_class.owner = parent_element
                prop.property_type = enum_class
        elif bits_type is not None and bits_type == stmt.search_one('type'):
                # we have to create the specific subclass of FixedBitsDict
                bits_class = Bits(self.iskeyword)
                bits_class.stmt = bits_type
                parent_element.owned_elements.append(bits_class)
                bits_class.owner = parent_element
                prop.property_type = bits_class
        elif union_type is not None and union_type == stmt.search_one('type'):
            def _add_union_type(union_type_stmt, parent_element):
                for contained_type in union_type_stmt.i_type_spec.types:
                    contained_enum_type = self.types_extractor.get_enum_type_stmt(contained_type)
                    contained_bits_type = self.types_extractor.get_bits_type_stmt(contained_type)
                    contained_union_type = self.types_extractor.get_union_type_stmt(contained_type)

                    if contained_enum_type is not None and contained_enum_type == contained_type:
                        enum_class = Enum(self.iskeyword)
                        enum_class.stmt = contained_enum_type
                        parent_element.owned_elements.append(enum_class)
                        enum_class.owner = parent_element
                        contained_enum_type.i_enum = enum_class

                    if contained_bits_type is not None and contained_bits_type == contained_type:
                        bits_class = Bits(self.iskeyword)
                        bits_class.stmt = contained_bits_type
                        parent_element.owned_elements.append(bits_class)
                        bits_class.owner = parent_element
                        contained_bits_type.i_bits = bits_class

                    if contained_union_type is not None and contained_union_type == contained_type:
                        _add_union_type(contained_union_type, parent_element)

            # is this embedded ?
            if union_type == stmt.search_one('type'):
                # we need to check for the types under the union to see if
                # any of them need to be handled differently
                _add_union_type(union_type, parent_element)


    def _create_expanded_api_model(self, stmt, parent_element, deviation_packages):
        """
            Converts the stmt to an Element in the api_model according
            to the expanded code generation algorithm.

            The expanded code generation algorithm uses the tree view of the YANG models
            to generate the API. For each data node in the YANG model a corresponding Class
            element will be created.

            In the first pass Elements that encapsulate the references are created
            this is done for all the stmts we are interested
            after this is done, resolve cross references is called on all the elements
            to resolve all the cross references (examples include
            super classes extends field in a class)

            :param `pyang.statements.Statement` stmt The statement to convert
            :param  `Element` The parent element.
            :param list of 'Package' The deviation packages.
        """

        # process typedefs first so that they are resolved
        # when we have to use them
        element = parent_element

        # identities
        if hasattr(stmt, 'i_identities'):
            for identity_stmt in stmt.i_identities.values():
                identity_class = Class(self.iskeyword)
                identity_class.stmt = identity_stmt
                identity_class.owner = parent_element
                parent_element.owned_elements.append(identity_class)
                identity_stmt.i_class = identity_class

        if hasattr(stmt, 'i_typedefs'):
            for typedef_stmt_name in stmt.i_typedefs:
                typedef_stmt = stmt.i_typedefs[typedef_stmt_name]
                self._add_enums_and_bits(typedef_stmt, parent_element)

        if stmt.keyword == 'module':
            pass

        elif stmt.keyword == 'container' or stmt.keyword == 'list' or stmt.keyword == 'rpc' or stmt.keyword == 'input' or stmt.keyword == 'output':
            if (stmt.keyword == 'input' or stmt.keyword == 'output') and len(stmt.substmts) == 0:
                pass
            else:
                clazz = Class(self.iskeyword)
                stmt.i_class = clazz
                clazz.stmt = stmt

                parent_element.owned_elements.append(clazz)
                clazz.owner = parent_element

                if name_matches_ancestor(clazz.name, parent_element):
                    clazz.name = clazz.name + '_'

                element = clazz

                if not isinstance(parent_element, Package):
                    # create a property along with the class
                    prop = Property(self.iskeyword)
                    stmt.i_property = prop
                    prop.stmt = stmt
                    prop.property_type = clazz
                    parent_element.owned_elements.append(prop)
                    prop.owner = parent_element

        elif stmt.keyword == 'leaf' or stmt.keyword == 'leaf-list' or stmt.keyword == 'anyxml':
            self._add_leaf_leaflist_prop(stmt, parent_element)

        if hasattr(stmt, 'i_deviation'):
            self._add_to_deviation_package(stmt, parent_element, deviation_packages)

        # walk the children
        _keywords = statements.data_definition_keywords + ['case', 'rpc', 'input', 'output']
        if hasattr(stmt, 'i_children'):
            self._sanitize_namespace(stmt)

            child_stmts=[]
            if hasattr(stmt, 'i_key') and stmt.i_key is not None:
                child_stmts.extend([s for s in stmt.i_key])

            if stmt.keyword == 'rpc' and self.language == 'cpp':
                child_stmts = self._walk_children(stmt, _keywords)

            else:
                _children = [child for child in stmt.i_children \
                    if (child not in child_stmts and child.keyword in _keywords)]
                child_stmts.extend(_children)

            for child_stmt in child_stmts:
                self._create_expanded_api_model(child_stmt, element, deviation_packages)

    # assumes stmt has attribute 'i_children' and language is 'cpp'
    def _walk_children(self, stmt, keywords):
        children = []

        if hasattr(stmt, 'i_key') and stmt.i_key is not None:
            children.extend([s for s in stmt.i_key if s not in children])

        black_sheep = []
        for child in stmt.i_children:
            if child not in children and child.keyword in keywords:
                if child.keyword == 'input':
                    black_sheep.append(child)
                else:
                    children.append(child)

        for child in black_sheep:
            children.extend(self._walk_children(child, keywords))

        return children


    def _sanitize_namespace(self, stmt):
        """
            Detects if there is a name clash for a statement
            under a given node.

            Note in the expanded tree algorithm
            augments show up under the parent node and their namespaces
            are not taken into account when the corresponding api_model.Element
            is generated. By sanitizing the namespace we avoid name collisions
            that can occur because of this situations

            :param `pyang.statements.Statement` The stmt to sanitize.
        """
        def _get_num_clashes(i_children):
            stmts = [stmt for stmt in i_children]
            clashes = []

            while len(stmts) > 0:
                stmt = stmts.pop()
                if stmt.arg in [s.arg for s in stmts] and stmt.arg not in clashes:
                    clashes.append(stmt.arg)

            return clashes

        def _kill_clash(clash, i_children):
            for stmt in i_children:
                if clash == stmt.arg:
                    old_arg = stmt.arg
                    new_arg = '%s_%s' % (stmt.top.arg, old_arg)
                    stmt.arg = new_arg

        clashes = _get_num_clashes(stmt.i_children)

        if len(clashes) > 0:
            for clash in clashes:
                _kill_clash(clash, stmt.i_children)


class GroupingClassApiModelBuilder(ApiModelBuilder):
    def generate(self, modules):
        """
            Generates and returns the packages for the list of modules supplied.

            This is the function that converts the list of pyang modules to
            Packages in the api_model for the grouping as classes strategy.

            :param list of `pyang.statements.Statement`

        """
        only_modules = [m for m in modules if m.keyword == 'module']
        packages = []
        for m in only_modules:
            p = Package(self.iskeyword)
            m.i_package = p
            p.stmt = m
            self._create_grouping_class_api_model(m, p)
            packages.append(p)

        # resolve cross references
        for p in packages:
            self._resolve_grouping_class_cross_references(p)
        return packages

    def _resolve_grouping_class_cross_references(self, element):
        """
            Resolve cross references in the grouping as class code generation
            strategy.

            :param `api_model.Element` The model element whose cross references have to be
                    resolved.

            :raise `common.YdkGenException' if cross resolution of references failed.

        """
        if isinstance(element, Class) and not element.is_identity():
            uses_stmts = element.stmt.search('uses')

            # set the super classes or the extend property
            groupings_used = []
            for uses in uses_stmts:
                groupings_used.append(uses.i_grouping)

            extends = []
            for grouping_stmt in groupings_used:
                if grouping_stmt.i_class is None:
                    raise YdkGenException(
                        'Unresolved grouping class for ' + element.fqn())
                extends.append(grouping_stmt.i_class)
            element._extends = extends
        if isinstance(element, Property):
            enum_type = self.types_extractor.get_enum_type_stmt(element.stmt)
            if enum_type is not None and not isinstance(element.property_type, Enum):
                if not hasattr(enum_type.parent, 'i_enum'):
                    raise YdkGenException(
                        'Cross resolution of enum failed for ' + element.fqn())

                element.property_type = enum_type.parent.i_enum

            else:
                # check for identity_ref's
                identity_ref_type = self.types_extractor.get_identity_ref_type_stmt(element.stmt)
                if identity_ref_type is not None:
                    element.property_type = identity_ref_type.i_type_spec.base.i_identity.i_class
                else:
                    # check for bits
                    bits_ref_type = self.types_extractor.get_bits_type_stmt(element.stmt)
                    if bits_ref_type is not None and not isinstance(element.property_type, Bits):
                        if not hasattr(bits_ref_type.parent, 'i_bits'):
                            raise YdkGenException(
                                'Cross resolution of bits failed for ' + element.fqn())

                        element.property_type = bits_ref_type.i_bits

        if hasattr(element, 'owned_elements'):
            for owned_element in element.owned_elements:
                self._resolve_grouping_class_cross_references(owned_element)


    def _create_grouping_class_api_model(self, stmt, parent_element):
        """
            Converts the stmt to an Element in the api_model according
            to the grouping as class algorithm.

            In the grouping as class code generations strategy a grouping in YANG
            is converted to a class. Every class that represents a container or a list
            or a grouping that has a uses statement in it , inherits from the grouping class that
            corresponds to the grouping in the uses statement.

            for example

            grouping abc {                        class Abc_Grouping(object):...
            ....
            }

            container A {                         class A(Abc_Grouping): ...
                uses abc;
            }

            In the first pass Elements that encapsulate the references are created
            this is done for all the stmts we are interested
            after this is done, resolve cross references is called on all the elements
            to resolve all the cross references (examples include
            super classes extends field in a class)

            :param `pyang.statements.Statement` stmt The statement to convert
            :param  `Element` The parent element.
        """
        # process typedefs first so that they are resolved
        # when we have to use them
        element = parent_element

        # identities
        if hasattr(stmt, 'i_identities'):
            for identity_stmt in stmt.i_identities.values():
                identity_class = Class(self.iskeyword)
                identity_class.stmt = identity_stmt
                identity_class.owner = parent_element
                parent_element.owned_elements.append(identity_class)
                identity_stmt.i_class = identity_class

        if hasattr(stmt, 'i_typedefs'):
            for typedef_stmt_name in stmt.i_typedefs:
                typedef_stmt = stmt.i_typedefs[typedef_stmt_name]
                self._add_enums_and_bits(typedef_stmt, parent_element)

        # walk the groupings first
        if hasattr(stmt, 'i_groupings'):
            for grouping_name in stmt.i_groupings:
                self._create_grouping_class_api_model(
                    stmt.i_groupings[grouping_name], element)

        if stmt.keyword == 'grouping':
            clazz = Class(self.iskeyword)
            stmt.i_class = clazz
            clazz.stmt = stmt
            parent_element.owned_elements.append(clazz)
            clazz.owner = parent_element
            element = clazz

        elif stmt.keyword == 'container' or stmt.keyword == 'list':
            clazz = Class(self.iskeyword)
            stmt.i_class = clazz
            clazz.stmt = stmt
            parent_element.owned_elements.append(clazz)
            clazz.owner = parent_element
            element = clazz

            if not isinstance(parent_element, Package):
                # create a property along with the class
                prop = Property(self.iskeyword)
                stmt.i_property = prop
                prop.stmt = stmt
                prop.property_type = clazz
                parent_element.owned_elements.append(prop)
                prop.owner = parent_element

        elif stmt.keyword == 'leaf' or stmt.keyword == 'leaf-list':
            prop = Property(self.iskeyword)
            stmt.i_property = prop
            prop.stmt = stmt
            parent_element.owned_elements.append(prop)
            prop.owner = parent_element
            # for inlined enum types where leaf { type enumeration {
            enum_type = self.types_extractor.get_enum_type_stmt(stmt)
            bits_type = self.types_extractor.get_bits_type_stmt(stmt)
            if enum_type is not None:
                if enum_type == stmt.search_one('type'):
                    # we have to create the enum
                    enum_class = Enum(self.iskeyword)
                    enum_class.stmt = enum_type
                    parent_element.owned_elements.append(enum_class)
                    enum_class.owner = parent_element
                    prop.property_type = enum_class
                    enum_type.parent.i_enum = enum_class
            elif bits_type is not None:
                if bits_type == stmt.search_one('type'):
                    # we have to create the specific subclass of FixedBitsDict
                    bits_class = Bits(self.iskeyword)
                    bits_class.stmt = bits_type
                    parent_element.owned_elements.append(bits_class)
                    bits_class.owner = parent_element
                    prop.property_type = bits_class

        # walk the children
        if hasattr(stmt, 'i_children'):
            grouping_stmt_names = []

            if stmt.keyword != 'module':
                uses_stmts = stmt.search('uses')
                groupings_used = []
                for uses_stmt in uses_stmts:
                    groupings_used.append(uses_stmt.i_grouping)

                for grouping in groupings_used:
                    grouping_stmt_names.extend(
                        [s.arg for s in grouping.i_children])

            chs = [ch for ch in stmt.i_children
                   if ch.keyword in statements.data_definition_keywords and ch.arg not in grouping_stmt_names]
            for child_stmt in chs:
                self._create_grouping_class_api_model(child_stmt, element)


class SubModuleBuilder(object):
    def generate(self, submodules, iskeyword):
        packages = []
        for sub in submodules:
            package = Package(iskeyword)
            sub.i_package = package
            package.stmt = sub
            packages.append(package)
        return packages


def name_matches_ancestor(name, parent_element):
    if parent_element is None or isinstance(parent_element, Package):
        return False

    if name == parent_element.name:
        return True

    if not hasattr(parent_element, 'owner'):
        return False

    return name_matches_ancestor(name, parent_element.owner)

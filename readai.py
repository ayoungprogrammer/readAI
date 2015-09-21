from nltk.parse import stanford
from nltk import Tree
import os
import sys
import getopt

# sys.path.append('~/Downloads/en') # put where you downloaded the nodebox/linguistics

import en

from nltk.parse import stanford

# Put where you downloaded the stanford-parser-full...
os.environ['STANFORD_PARSER'] = '.' #'~/Downloads/stanford-parser-full-2015-04-20/'
os.environ['STANFORD_MODELS'] = '.' #'~/Downloads/stanford-parser-full-2015-04-20/'

smap = {}


class Node(list):
    def __init__(self, label):
        self.label = label
        self.prev = DummyNode()

    def set(self, key, value):
        self.append((key, value))
        if isinstance(value.prev, DummyNode):
            value.prev = self

    def get(self, key):
        for k, v in self:
            if key == k:
                return v
        return DummyNode()

    def complete(self, tokens, qtype):
        # print tokens
        if len(tokens) == 0:
            if qtype.lower() == "why":
                cur_node = self.get('because') or self.get('since')
                ret = [cur_node.label]

                cur_node = cur_node.get('.')
                prev_node = cur_node.prev
                while prev_node.label not in smap:
                    ret.append(prev_node.label)
                    prev_node = prev_node.prev
                ret.append(prev_node.label)

                while cur_node.label not in smap and len(cur_node) > 0:
                    ret.append(cur_node.label)
                    cur_node = cur_node[0][1]
                ret.append(cur_node.label)
                return ' '.join(ret)

            else:
                if self.label in smap:
                    return self.label
                if not isinstance(self.get('.'), DummyNode):
                    return self.get('.').label
                elif len(self) > 0:
                    return self[0][0] + " " + self[0][1].complete(tokens, qtype)
                else:
                    return "Unsure"
        else:
            token = get_word(tokens[0])
            if tokens[0].label() in ["VB", "VBD", "VBZ"]:
                token = get_root_word(token)
            if tokens[0].label() == "NP":
                return self.complete(tokens[1:], qtype)

            for k, v in self:
                if k == token:
                    return v.complete(tokens[1:], qtype)
            return "Answer unclear"

    def matches(self, tokens):
        # print tokens
        if len(tokens) == 0:
            return True

        if tokens[0].label() == "NP":
            if not isinstance(self.get('.'), DummyNode):
                return self.get('.').matches(tokens)
            if self.label != get_word(tokens[0]).upper():
                return False
            else:
                return self.matches(tokens[1:])

        token = get_word(tokens[0])
        if tokens[0].label() in ["VB", "VBD", "VBZ"]:
            token = get_root_word(token)

        for k, v in self:
            if k == token:
                return v.matches(tokens[1:])
        return False


class DummyNode(Node):

    def __init__(self):
        self.label = "Answer unclear"

    def get(self, key):
        return self

    def __nonzero__(self):
        return False


def get_word(tree):
    if isinstance(tree, Tree):
        words = []
        for child in tree:
            words.append(get_word(child))
        return ' '.join(words)
    else:
        return tree


def get_root_word(word):
    if word in ['is', 'was']:
        return 'is'
    return en.verb.present(word)


def get_node(label):
    if label not in smap:
        smap[label] = Node(label)
    return smap[label]


def flatten_tree(tree):
    # print tree
    if len(tree) > 0:
        if isinstance(tree[0], Tree):
            if isinstance(tree, Tree) and tree.label() == "NP":
                return [tree]
            tokens = []
            for child in tree:
                tokens += flatten_tree(child)
            return tokens
        else:
            return [tree]
    else:
        return []


def get_tokens(tokens):
    tokens = tokens[1:-1]
    ret = []
    start = 0
    stack = 0
    for i in xrange(len(tokens)):
        if tokens[i] == "(":
            if stack == 0:
                start = i
            stack += 1
        elif tokens[i] == ")":
            stack -= 1
            if stack < 0:
                print "Brack mismatch: " + str(tokens)
            if stack == 0:
                ret.append(get_tokens(tokens[start:i + 1]))
        else:
            if stack == 0:
                ret.append(tokens[i])
    if stack != 0:
        print "Bracket mismatch: " + str(tokens)
    return ret


def matches(match_str, tree):
    tokens = get_tokens(match_str.split())
    return match_tokens(tokens, tree)


def match_tokens(tokens, tree):

    if len(tokens) == 0:
        return True

    if tokens[0] is not '.' and tree.label() not in tokens[0].split('/'):
        return False

    if tokens[-1] == '$':
        if len(tree) != len(tokens[:-1]) - 1:
            return False
        else:
            tokens = tokens[:-1]

    if len(tree) < len(tokens) - 1:
        return False

    for i in xrange(len(tokens) - 1):
        if not match_tokens(tokens[i + 1], tree[i]):
            return False
    return True

# Returns subject


def describe(tree):

    if not isinstance(tree, Tree):
        print "ERROR"
    if tree.label() == "ROOT":
        describe(tree[0])
        return

    # Augment data
    if matches('( S ( NP ) ( VP ( VBP ) ( ADJP ) ) )', tree):
        _, subject = describe(tree[0])
        action = get_root_word(get_word(tree[1][0]))
        action_node = Node(action)
        adj = get_word(tree[1][1])
        adj_node = Node(adj)

    # Sentences
    if matches('( S ( NP ) ( VP ) )', tree):
        _, subject = describe(tree[0])
        action, action_node = describe(tree[1])

        subject.set(action, action_node)
        return action, action_node
    if matches('( S ( VP ) )', tree):
        return describe(tree[0])

    # NOUNS
    if matches('( NP )', tree):
        # Ex: The dog
        word = get_word(tree).upper()
        return word, get_node(word)

    # PROPOSITIONS
    if matches('( PP ( . ) ( NP ) )', tree):
        # to the mall
        # with her parents
        _, obj = describe(tree[1])
        prop = get_word(tree[0])

        return prop, obj
    if matches('( PRT )', tree):
        prt = get_word(tree)
        return prt, Node(prt)

    # VERBS
    if matches('( VP ( VBD ) ( VP ) $ )', tree):
        action = get_root_word(get_word(tree[0]))

        return action, Node(action)

    if matches('( VP ( VB/VBD ) $ )', tree):
        action = get_root_word(get_word(tree))
        return action, Node(action)

    if matches('( VP ( VB/VBZ/VBP/VPZ/VBD/VBG/VBN ) ( PP ) )', tree):
        action = get_root_word(get_word(tree[0]))
        action_node = Node(action)
        prop, prop_node = describe(tree[1])
        action_node.set(prop, prop_node)
        return action, action_node

    if matches('( VP ( VB/VBZ/VBP/VPZ/VBD/VBG/VBN ) ( PRT ) ( NP ) )', tree):
        action = get_root_word(get_word(tree[0]))
        action_node = Node(action)
        prt, prt_node = describe(tree[1])
        action_node.set(prt, prt_node)
        _, obj = describe(tree[2])
        prt_node.set('.', obj)
        return action, action_node

    if matches('( VP ( VB/VBZ/VBP/VPZ/VBD/VBG/VBN ) ( NP ) )', tree):
        action = get_root_word(get_word(tree[0]))
        action_node = Node(action)

        _, obj = describe(tree[1])
        action_node.set('.', obj)

        if matches('( VP ( VB/VBZ/VBP/VPZ/VBD/VBG/VBN ) ( NP ) ( PP ) )', tree):
            # Assume rest is PP
            for pp_node in tree[2:]:
                prop, prop_node = describe(pp_node)
                action_node.set(prop, prop_node)

        if matches('( VP ( VB/VBZ/VBP/VPZ/VBD/VBG/VBN ) ( NP ) ( SBAR ) )', tree):
            # SBAR at end
            sbar, sbar_node = describe(tree[2])
            action_node.set(sbar, sbar_node)


        return action, action_node

    if matches('( VP ( VB/VBZ/VBP/VPZ/VBD/VBG ) ( S ) )', tree):
        s, s_node = describe(tree[1])
        action = get_root_word(get_word(tree[0]))
        action_node = Node(action)

        action_node.set(s, s_node)
        return action, action_node

    if matches('( VP ( TO ) ( VP ) )', tree):
        to_node = Node('to')
        action, action_node = describe(tree[1])

        to_node.set(action, action_node)

        return 'to', to_node

    if matches('( VP ( VB/VBZ/VBP/VPZ/VBD/VBG/VBN ) ( ADJP ) )', tree):
        action = get_root_word(get_word(tree[0]))
        action_node = Node(action)

        adj = get_node(get_word(tree[1]))

        action_node.set('.', adj)
        return action, action_node
    if matches('( VP ( VB/VBZ/VBP/VPZ/VBD/VBG/VBN ) ( SBAR ) )', tree):
        action = get_root_word(get_word(tree[0]))
        action_node = Node(action)

        sbar, sbar_node = describe(tree[1])
        action_node.set(sbar, sbar_node)
        return action, action_node

    # SBAR
    if matches('( SBAR ( IN ) ( S ) )', tree):
        prop = get_word(tree[0])
        prop_node = Node(prop)
        s, s_node = describe(tree[1])

        prop_node.set('.', s_node)

        return prop, prop_node

    raise ValueError("ERROR reading " + str(tree))


def answer(tree):
    tree = tree[0]
    if tree.label() != "SBARQ":
        print "ERROR not a question: " + str(tree)
        return None

    # What did Mary / Where did Mary ( ... )
    if matches('( SBARQ ( WHNP/WHADVP ) ( SQ ( VBZ/VBD/VBP ) ( NP ) ) )', tree):

        qtype = get_word(tree[0])
        subject = get_word(tree[1][1]).upper()
        verb = get_root_word(get_word(tree[1][0]))

        if verb is 'is':
            return get_node(subject).get('is').complete([], qtype)
        else:
            tokens = flatten_tree(tree[1][2:])
            return get_node(subject).complete(tokens, qtype)

    # What has blue eyes
    if matches('( SBARQ ( WHNP ) ( SQ ( VP/VBZ ) ) )', tree):
        tokens = flatten_tree(tree[1])
        objs = []
        for obj in smap:
            if smap[obj].matches(tokens):
                objs.append(obj)

        if len(objs) == 0:
            return "Nothing"
        return ','.join(objs)

    print "ERROR answering"

def usage():
    print "Usage: " + sys.argv[0] + " [-d]"

def main(argv):

    debug = False

    try:
        opts, args = getopt.getopt(argv, "hd",["help","debug"])
    except getopt.GetoptError as e:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ["-h", "help"]:
            usage()
            sys.exit(2)
        if opt in ["-d", "debug"]:
            debug = True

    parser = stanford.StanfordParser()

    line = raw_input("Enter line: ")

    while line != 'stop':
        sent = list(parser.raw_parse(line))[0]
        if debug:
            print sent # print parse tree
        if sent[0].label() == "SBARQ":
            print answer(sent)
        else:
            try:
                describe(sent)
            except ValueError as e:
                print "Error describing sentence. " + e
            if debug:
                print smap # print semantic map
        line = raw_input("Enter line: ")


if __name__ == "__main__":
    main(sys.argv[1:])

# Example:
"""
Mary went sledding
Where did Mary go? sledding

The boy played soccer with a ball
What did the boy play? soccer
What did the boy play soccer with? a ball

Mary went to the mall
Where did Mary go? to the mall
Where did Mary go to? the mall

Mary likes eating peanuts
What does Mary like eating? peanuts
What does Mary like? eating peanuts

Mary likes to eat peanuts
What does Mary like? To eat peanuts
What does Mary like to eat? peanuts

Mark likes to smoke
What does Mary like? to smoke

Blueberries are blue
What color are blueberries? blue

James ran because James was scared
Why did James run? because James was scared
"""

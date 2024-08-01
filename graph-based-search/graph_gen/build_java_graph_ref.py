import os
import sys
import json
import gzip
import codecs
import re
import pickle
import multiprocessing as mp
from pathlib import Path
from subprocess import Popen, PIPE
from tqdm import tqdm
import networkx as nx
from collections import defaultdict
import spacy

class JavaGraphBuilder:
    def __init__(self):
        self.dir_path = os.path.dirname(os.path.realpath(__file__))
        self.home_path = str(Path.home())
        self.environ = os.environ.copy()
        self.environ['JAVA_HOME'] = '/usr/lib/jvm/jdk-11-oracle-x64'
        self.environ['PATH'] += ':/usr/lib/jvm/jdk-11-oracle-x64/bin'
        
        self.EXTRACTOR_JAR = '/home/t-anthonyp/repos/features-javac/extractor/target/features-javac-extractor-1.0.0-SNAPSHOT-jar-with-dependencies.jar'
        self.DOT_JAR = '/home/t-anthonyp/repos/features-javac/dot/target/features-javac-dot-1.0.0-SNAPSHOT-jar-with-dependencies.jar'
        self.RAW_FILE = os.path.join(self.home_path, 'data/code_search_data/CodeSearchNet/resources/data/java/final/jsonl')
        self.JAVA_BASE = os.path.join(self.home_path, 'data/code_search_data/CodeSearchNet/resources/data/java_dedupe_definitions_v2.pkl')
        self.JAVA_BASE_DIR = os.path.join(self.home_path, 'data/code_search_data/CodeSearchNet/resources/data/java_base')
        self.BASE_GRAPH_FILE = os.path.join(self.home_path, 'data/code_search_data/CodeSearchNet/resources/data/java_base_gz')

        self.nlp = spacy.load("en_core_web_sm")
        self.nlp.tokenizer = self.WhitespaceTokenizer(self.nlp.vocab)

    class WhitespaceTokenizer:
        def __init__(self, vocab):
            self.vocab = vocab

        def __call__(self, text):
            words = text.split(' ')
            spaces = [True] * len(words)
            return spacy.tokens.Doc(self.vocab, words=words, spaces=spaces)

    def load_jsonl_gz(self, file_path):
        reader = codecs.getreader('utf-8')
        data = []
        with gzip.open(file_path) as f:
            json_list = list(reader(f))
        data.extend([json.loads(jline) for jline in json_list])
        return data

    def check_existed(self, sample, java_func_dir):
        couple = sample['url'].split('/')[-1].split('#')
        class_name = couple[0].split('.java')[0]
        start, end = couple[1].split('-')
        start, end = start.replace('L', ''), end.replace('L', '')
        project = sample.get('repo', sample.get('nwo', '')).replace('/', '-')
        file_name = os.path.join(java_func_dir, f"{project}_{class_name}_{start}_{end}")
        return os.path.exists(file_name)

    def write_sample_to_java_file(self, sample, java_func_dir):
        couple = sample['url'].split('/')[-1].split('#')
        class_name = couple[0].split('.java')[0]
        start, end = couple[1].split('-')
        start, end = start.replace('L', ''), end.replace('L', '')
        project = sample.get('repo', sample.get('nwo', '')).replace('/', '-')
        file_name = os.path.join(java_func_dir, f"{project}_{class_name}_{start}_{end}")
        
        os.makedirs(file_name, exist_ok=True)
        
        function_text = sample.get('code', sample.get('function', ''))
        function_text = self.wrap_function_dummy_class(function_text, class_name)
        
        wrapped_file_path = self.write_wrapped_function(function_text, class_name, file_name)
        self.write_json(sample, os.path.join(file_name, f"{class_name}.json"))
        
        return wrapped_file_path, file_name

    def write_wrapped_function(self, function_text, class_name, file_name):
        wrapped_file_path = os.path.join(file_name, f"{class_name}.java")
        with open(wrapped_file_path, 'w', encoding='utf-8') as writer:
            writer.write(function_text)
        return wrapped_file_path

    def wrap_function_dummy_class(self, function_text, class_name):
        return f'public class {class_name} {{ \n{function_text}\n }}'

    def write_json(self, data, file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def build_java_graphs(self):
        types = os.listdir(self.RAW_FILE)
        for type in types:
            samples = []
            type_dir = os.path.join(self.RAW_FILE, type)
            for file in os.listdir(type_dir):
                if file.endswith('.gz') and file.startswith('java'):
                    samples.extend(self.load_jsonl_gz(os.path.join(type_dir, file)))
            
            java_func_dir = os.path.join(type_dir, 'java_funcs')
            os.makedirs(java_func_dir, exist_ok=True)
            
            results = self.parallel_process(samples, self.build_single_graph, args=(java_func_dir, True), n_cores=1)
            succeed = sum(1 for result in results if result)
            print(f'{type} built {succeed} graphs totally')
            break

    def build_single_graph(self, sample, java_func_dir, override=False):
        try:
            if 'function_tokens' in sample and len(sample['function_tokens']) > 200:
                return False
            if self.check_existed(sample, java_func_dir) and not override:
                return False
            
            wrapped_file_path, file_name = self.write_sample_to_java_file(sample, java_func_dir)
            print("file_name: ", file_name)
            print("wrapped_file_path: ", wrapped_file_path)
            self.generate_proto_file(wrapped_file_path)
            
            if os.path.exists(wrapped_file_path + '.proto'):
                self.generate_dot_json_file(wrapped_file_path)
                print("dot json file generated")
                sys.exit(0)
                return True
            sys.exit(0)
            return False
        except Exception as e:
            print(e)
            sys.exit(0)
            return False

    def parallel_process(self, array, function, args=(), n_cores=None):
        if n_cores == 1:
            return [function(x, *args) for x in tqdm(array)]
        
        with tqdm(total=len(array), desc="Parallel Process") as pbar:
            def update(*args):
                pbar.update()
            
            if n_cores is None:
                n_cores = mp.cpu_count()
            
            with mp.Pool(processes=n_cores) as pool:
                jobs = [pool.apply_async(function, (x, *args), callback=update) for x in array]
                results = [job.get() for job in jobs]
            
            return results

    def generate_proto_file(self, wrapped_file_path):
        command = f'/usr/lib/jvm/jdk-11-oracle-x64/bin/javac -cp {self.EXTRACTOR_JAR} -Xplugin:FeaturePlugin {wrapped_file_path}'
        p1 = Popen(command, cwd='/', shell=True, env=self.environ, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p1.communicate()
        
        if p1.returncode == 0:
            print(f"Success: {wrapped_file_path} processed successfully.")
        else:
            print(f"Error: {wrapped_file_path} processing failed.")
            print(f"Command: {command}")
            print(f"Return code: {p1.returncode}")
            if stdout:
                print(f"Standard Output:\n{stdout.decode('utf-8')}")
            if stderr:
                print(f"Standard Error:\n{stderr.decode('utf-8')}")

    def generate_dot_json_file(self, wrapped_file_path):
        command = f'/usr/lib/jvm/jdk-11-oracle-x64/bin/java -jar {self.DOT_JAR} -i {wrapped_file_path}.proto -o {wrapped_file_path}.dot -j {wrapped_file_path}.json'
        p1 = Popen(command, cwd='/', shell=True, env=self.environ, stdout=PIPE, stderr=PIPE)
        p1.communicate()

    # ... (other methods like normalize_graph, subtokenizer, post_process, etc. would be implemented similarly)

if __name__ == '__main__':
    graph_builder = JavaGraphBuilder()
    graph_builder.build_java_graphs()
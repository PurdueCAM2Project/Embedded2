#!/usr/bin/env python3
from setuptools import setup, Extension
from torch.utils import cpp_extension
import os

print(os.getcwd())
setup(
        name='video_encode',
        ext_modules=[
            cpp_extension.CppExtension('video_encode', ['video_encode.cpp'],
                                        extra_compile_args = ['-Wall','-g', '-O0'],
                                        library_dirs = ['/usr/local/cuda/lib64', ],
                                        libraries = ['NvPipe']
            )
        ],
        cmdclass={'build_ext': cpp_extension.BuildExtension},
        include_dirs = ['/usr/local/cuda/include'],
        install_requires=['torch>=1.3']
     )
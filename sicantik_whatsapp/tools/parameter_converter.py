# -*- coding: utf-8 -*-

"""
Parameter Converter Utility

Utility untuk konversi parameter dari format generik (placeholder bernama)
ke format yang dibutuhkan masing-masing provider (indexed parameters).
"""

import logging

_logger = logging.getLogger(__name__)


class ParameterConverter:
    """
    Converter untuk parameter template WhatsApp
    """
    
    @staticmethod
    def generic_to_meta(parameter_list, context_values):
        """
        Convert parameter generik ke format Meta WhatsApp API
        
        Meta format:
        {
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "value1"},
                    {"type": "text", "text": "value2"},
                    ...
                ]
            }]
        }
        
        Args:
            parameter_list (list): List parameter names ['partner_name', 'permit_number', ...]
            context_values (dict): Dictionary nilai {'partner_name': 'John', 'permit_number': '123', ...}
        
        Returns:
            dict: Format Meta API
        """
        parameters = []
        
        for param_name in parameter_list:
            value = context_values.get(param_name, '')
            parameters.append({
                "type": "text",
                "text": str(value)
            })
        
        return {
            "components": [{
                "type": "body",
                "parameters": parameters
            }]
        }
    
    @staticmethod
    def generic_to_watzap(parameter_list, context_values):
        """
        Convert parameter generik ke format Watzap.id API
        
        Watzap format (based on API docs):
        {
            "parameters": {
                "1": "value1",
                "2": "value2",
                ...
            }
        }
        
        Args:
            parameter_list (list): List parameter names
            context_values (dict): Dictionary nilai
        
        Returns:
            dict: Format Watzap API
        """
        parameters = {}
        
        for idx, param_name in enumerate(parameter_list, start=1):
            value = context_values.get(param_name, '')
            parameters[str(idx)] = str(value)
        
        return {
            "parameters": parameters
        }
    
    @staticmethod
    def generic_to_fonnte(parameter_list, context_values):
        """
        Convert parameter generik ke format Fonnte API
        
        Fonnte format (assumed similar to Watzap):
        {
            "var1": "value1",
            "var2": "value2",
            ...
        }
        
        Args:
            parameter_list (list): List parameter names
            context_values (dict): Dictionary nilai
        
        Returns:
            dict: Format Fonnte API
        """
        parameters = {}
        
        for idx, param_name in enumerate(parameter_list, start=1):
            value = context_values.get(param_name, '')
            parameters[f"var{idx}"] = str(value)
        
        return parameters
    
    @staticmethod
    def validate_context_values(parameter_list, context_values):
        """
        Validate bahwa semua parameter yang dibutuhkan tersedia di context
        
        Args:
            parameter_list (list): List parameter names
            context_values (dict): Dictionary nilai
        
        Returns:
            tuple: (is_valid: bool, missing_params: list)
        """
        missing = []
        
        for param_name in parameter_list:
            if param_name not in context_values or not context_values[param_name]:
                missing.append(param_name)
        
        return (len(missing) == 0, missing)


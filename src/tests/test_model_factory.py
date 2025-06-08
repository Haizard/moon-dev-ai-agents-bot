import unittest
from unittest.mock import patch, MagicMock
import os

# Ensure PYTHONPATH is set up correctly if running tests from a different directory
# For example, if tests are in 'src/tests' and modules are in 'src',
# you might need to adjust sys.path or run with 'python -m unittest src.tests.test_model_factory'
# from the project root.

# Temporarily modify sys.path for testing if needed, assuming 'src' is the parent of 'tests'
import sys
# current_dir = os.path.dirname(os.path.abspath(__file__))
# project_root = os.path.dirname(current_dir) # This would be 'src'
# sys.path.insert(0, os.path.dirname(project_root)) # This would be the directory containing 'src'

# Assuming tests are run from the project root where 'src' is a subdirectory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


from src.models.base_model import BaseModel, ModelResponse
from src.models.groq_model import GroqModel
from src.models.gemini_model import GeminiModel
from src.models.openai_model import OpenAIModel
from src.models.claude_model import ClaudeModel
from src.models.deepseek_model import DeepSeekModel

# Import the singleton instance
# Important: This means model_factory is initialized ONCE when this test module is first imported.
# Its internal state (like self.core_model_type from config) is set at that time.
from src.models.model_factory import model_factory, ModelFactory
from src import config # To allow modification of config values for testing core model logic


class TestModelFactory(unittest.TestCase):

    def setUp(self):
        # Reset relevant parts of the model_factory instance before each test
        # This is crucial because model_factory is a singleton and retains state.
        model_factory._models = {} # Clear cached model instances

        # Store original config values to restore them later
        self.original_core_model_type = getattr(config, 'CORE_AI_MODEL_TYPE', None)
        self.original_core_model_name = getattr(config, 'CORE_AI_MODEL_NAME', None)

        # Also reset the factory's direct attributes that are set from config
        model_factory.core_model_type = self.original_core_model_type
        model_factory.core_model_name = self.original_core_model_name


    def tearDown(self):
        # Restore original config values after each test
        config.CORE_AI_MODEL_TYPE = self.original_core_model_type
        config.CORE_AI_MODEL_NAME = self.original_core_model_name
        # And restore them on the factory instance too
        model_factory.core_model_type = self.original_core_model_type
        model_factory.core_model_name = self.original_core_model_name
        model_factory._models = {} # Clean up models cache

    # --- Test Model Availability and get_model() ---

    @patch('os.getenv')
    def test_get_model_groq_available(self, mock_getenv):
        mock_getenv.return_value = "fake_groq_api_key" # Simulate API key is present

        # We need to ensure _initialize_models is called with the mock in place,
        # or that get_model triggers initialization if needed.
        # Since _initialize_models is called in __init__, and factory is a singleton,
        # we might need to manually re-trigger parts of initialization or mock client directly.
        # For simplicity, let's mock the specific model's client init.
        with patch('groq.Groq') as mock_groq_client:
            mock_groq_client.return_value.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="Test"))])

            # Re-initialize models for this specific test case with the mock effective
            model_factory._models = {} # Clear previous
            model_factory._initialize_models() # This will use the mocked os.getenv

            model = model_factory.get_model("groq")
            self.assertIsNotNone(model)
            self.assertIsInstance(model, GroqModel)
            self.assertTrue(model_factory.is_model_available("groq"))

    @patch('os.getenv')
    def test_get_model_groq_unavailable_no_key(self, mock_getenv):
        mock_getenv.return_value = None # Simulate API key is NOT present
        model_factory._models = {}
        model_factory._initialize_models() # Re-initialize with no key

        model = model_factory.get_model("groq")
        self.assertIsNone(model)
        self.assertFalse(model_factory.is_model_available("groq"))

    @patch('os.getenv')
    @patch('google.generativeai.GenerativeModel') # Mock the client initialization for Gemini
    def test_get_model_gemini_available(self, mock_genai_model, mock_getenv):
        mock_getenv.return_value = "fake_gemini_api_key"
        # Mock the behavior of the Gemini client if its methods are called during init
        mock_genai_model.return_value.generate_content.return_value = MagicMock(text="Test")

        model_factory._models = {}
        model_factory._initialize_models()

        model = model_factory.get_model("gemini")
        self.assertIsNotNone(model)
        self.assertIsInstance(model, GeminiModel)
        self.assertTrue(model_factory.is_model_available("gemini"))

    def test_get_model_invalid_type(self):
        model = model_factory.get_model("non_existent_model_type")
        self.assertIsNone(model)

    @patch('os.getenv')
    @patch('openai.OpenAI') # Mock the client initialization for OpenAI
    def test_get_model_openai_with_specific_name(self, mock_openai_client, mock_getenv):
        mock_getenv.return_value = "fake_openai_api_key"
        # Mock OpenAI client behavior if needed for initialization checks
        mock_openai_client.return_value.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="Test"))])

        model_factory._models = {}
        # _initialize_models initializes default models. get_model reinitializes if name differs.
        model_factory._initialize_models()


        # Assuming "gpt-4o" is a valid name for OpenAIModel type
        # And that the factory's default for "openai" might be different,
        # thus triggering re-initialization.
        model = model_factory.get_model("openai", model_name="gpt-4o")
        self.assertIsNotNone(model)
        self.assertIsInstance(model, OpenAIModel)
        self.assertEqual(model.model_name, "gpt-4o")
        self.assertTrue(model_factory.is_model_available("openai"))


    # --- Test get_core_model() ---

    @patch('os.getenv')
    @patch('groq.Groq')
    def test_get_core_model_groq_set_in_factory(self, mock_groq_client, mock_getenv):
        mock_getenv.return_value = "fake_groq_key" # API key for Groq
        mock_groq_client.return_value.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="Test"))])

        # Simulate that config had set these values when model_factory was initialized
        model_factory.core_model_type = "groq"
        model_factory.core_model_name = "mixtral-8x7b-32768" # A known Groq model

        # Ensure factory initializes this model if not cached
        model_factory._models = {} # Clear cache
        # _initialize_models might not pick up factory.core_model_type directly for pre-caching.
        # get_core_model itself calls get_model, which will initialize.

        core_model = model_factory.get_core_model()
        self.assertIsNotNone(core_model)
        self.assertIsInstance(core_model, GroqModel)
        self.assertEqual(core_model.model_name, "mixtral-8x7b-32768")

    @patch('os.getenv')
    @patch('google.generativeai.GenerativeModel')
    def test_get_core_model_gemini_set_in_factory_default_name(self, mock_genai_model, mock_getenv):
        mock_getenv.return_value = "fake_gemini_key"
        mock_genai_model.return_value.generate_content.return_value = MagicMock(text="Test")

        model_factory.core_model_type = "gemini"
        model_factory.core_model_name = None # Test factory's default name for Gemini

        model_factory._models = {}

        core_model = model_factory.get_core_model()
        self.assertIsNotNone(core_model)
        self.assertIsInstance(core_model, GeminiModel)
        # Check against the actual default name used by GeminiModel or ModelFactory for "gemini"
        # For GeminiModel, the default is "gemini-pro" if model_name not passed to constructor.
        # ModelFactory.DEFAULT_MODELS["gemini"] is "gemini-2.0-flash-exp"
        # get_model(type, None) uses DEFAULT_MODELS[type]
        self.assertEqual(core_model.model_name, ModelFactory.DEFAULT_MODELS["gemini"])


    def test_get_core_model_type_not_set_in_factory(self):
        model_factory.core_model_type = None
        model_factory.core_model_name = None
        core_model = model_factory.get_core_model()
        self.assertIsNone(core_model)

    @patch('os.getenv')
    def test_get_core_model_key_not_set_for_core_type(self, mock_getenv):
        mock_getenv.return_value = None # Simulate no API key for the core model type

        model_factory.core_model_type = "groq" # Set a core model type
        model_factory.core_model_name = None

        model_factory._models = {} # Clear cache
        # Re-run _initialize_models with the getenv mock returning None for GROQ_API_KEY
        model_factory._initialize_models()

        core_model = model_factory.get_core_model()
        self.assertIsNone(core_model) # get_model should return None, so get_core_model should too

    # --- Test Model Initialization Failures ---

    @patch('os.getenv')
    @patch('groq.Groq') # Target the client initialization
    def test_get_model_groq_init_raises_exception(self, mock_groq_constructor, mock_getenv):
        mock_getenv.return_value = "fake_groq_api_key"
        mock_groq_constructor.side_effect = Exception("Simulated Groq client init failure")

        model_factory._models = {}
        # _initialize_models will attempt to create GroqModel, which will fail
        # The error should be caught inside _initialize_models or get_model
        model_factory._initialize_models()

        model = model_factory.get_model("groq")
        self.assertIsNone(model)
        self.assertFalse(model_factory.is_model_available("groq"))

    @patch('os.getenv')
    @patch('google.generativeai.configure') # Patching 'configure' which is called before client
    def test_get_model_gemini_configure_raises_exception(self, mock_genai_configure, mock_getenv):
        mock_getenv.return_value = "fake_gemini_key"
        mock_genai_configure.side_effect = Exception("Simulated genai.configure failure")

        model_factory._models = {}
        model_factory._initialize_models()

        model = model_factory.get_model("gemini")
        self.assertIsNone(model) # Expect None because initialization failed
        self.assertFalse(model_factory.is_model_available("gemini"))


if __name__ == '__main__':
    unittest.main()

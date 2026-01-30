from workflow_manager import WorkflowManager

def main():
    # User input requirement
    user_query = "The Diffusion Transformer (DiT) architecture. Left: We train conditional latent DiT models. The input latent is decomposed into patches and processed by several DiT blocks. Right: Details of our DiT blocks. We experiment with variants of standard transformer blocks that incorporate conditioning via adaptive layer norm, cross-attention and extra input tokens. Adaptive layer norm works best."

    # ==========================================
    # Runtime Configuration
    # ==========================================
    
    # Output directory
    # None:  Automatically create new directory based on timestamp (recommended, prevents overwriting)
    # Path string: Specify a particular directory (e.g., "./output/test_run")
    CUSTOM_OUTPUT_DIR = None 

    # ==========================================
    # Execute Pipeline
    # ==========================================
    manager = WorkflowManager()
    
    print(f"🚀 Starting task...")
    
    # Call the run interface and receive return value
    success, message = manager.run(
        user_requirement=user_query, 
        output_dir=CUSTOM_OUTPUT_DIR
    )

    # ==========================================
    # Result Processing
    # ==========================================
    if success:
        print(f"\n✅ Program execution successful: {message}")
    else:
        print(f"\n❌ Program execution failed: {message}")

if __name__ == "__main__":
    main()

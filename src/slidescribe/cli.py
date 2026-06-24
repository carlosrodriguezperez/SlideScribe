import argparse
import sys
from slidescribe import __version__

def main():
    parser = argparse.ArgumentParser(description="SlideScribe CLI - Convert Lecture PDFs to Markdown")
    parser.add_argument(
        "--version", 
        action="store_true", 
        help="Print the version number and exit."
    )
    # Add a positional argument for the target PDF (for future phases)
    parser.add_argument(
        "target",
        nargs="?",
        help="Path to the source PDF file."
    )

    args = parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)
    
    if args.target:
        print(f"Target PDF: {args.target}")
        sys.exit(0)
    
    # If no arguments provided, print help
    parser.print_help()

if __name__ == "__main__":
    main()

import os
import shutil

def build_dist():
    print("Building production distribution in ./dist and ./docs ...")
    base_dir = os.path.dirname(__file__)
    dist_dir = os.path.join(base_dir, "dist")
    docs_dir = os.path.join(base_dir, "docs")
    frontend_dir = os.path.join(base_dir, "frontend")

    for target in [dist_dir, docs_dir]:
        if os.path.exists(target):
            shutil.rmtree(target)
        shutil.copytree(frontend_dir, target)
        print(f"[SUCCESS] Built production bundle at {target}")

    print("All deployment outputs generated successfully!")
    print(f"Generated files:")
    for root, dirs, files in os.walk(dist_dir):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), dist_dir)
            print(f"  - dist/{rel}")

if __name__ == "__main__":
    build_dist()

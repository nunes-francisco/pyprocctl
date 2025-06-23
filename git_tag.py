from git import Repo


def get_current_tag():
    try:
        repo = Repo('.')
        if repo.head.is_detached:
            tag = next((tag for tag in repo.tags if tag.commit == repo.head.commit), None)
        else:
            tag = next((tag for tag in repo.tags if tag.commit == repo.head.commit), None)

        return tag.name if tag else 'INDEFINIDO'
    except Exception as err:
        return str(err)
    

if __name__ == '__main__':
    print(get_current_tag())
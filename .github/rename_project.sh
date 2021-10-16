#!/usr/bin/env bash
# =============================================================================
# @file    rename_project.sh
# @brief   Shell script used in GitHub workflow for naming new projects
# @created 2021-10-14
# @license Please see the file named LICENSE in the project directory
# @website https://github.com/caltechlibrary/py-cli-template
#
# This file was originally based on the file of the same name in the repo
# https://github.com/rochacbruno/python-project-template by Bruno Rocha.
# The original file was copied on 2021-10-14.
# =============================================================================

while getopts a:n:u:d: flag
do
    case "${flag}" in
        a) author=${OPTARG};;
        n) project_name=${OPTARG};;
        u) urlname=${OPTARG};;
        d) description=${OPTARG};;
    esac
done

first_name=$(echo $author | /usr/bin/awk '{print $1}' | tr -d '"')
family_name=$(echo $author | /usr/bin/awk '{print $NF}' | tr -d '"')

creation_date=$(date +"%Y-%m-%d")
creation_year=$(date +"%Y")

echo "Author name: $author"
echo "Author first name: $first_name"
echo "Author family name: $family_name"
echo "Project name: $project_name"
echo "Project URL name: $urlname"
echo "Description: $description"
echo "Creation date: $creation_date"
echo "Creation year: $creation_year"

echo "Renaming project ..."

for filename in $(git ls-files)
do
    sed -i "s/%AUTHOR_NAME%/$author/g" $filename
    sed -i "s/%AUTHOR_FIRST_NAME%/$first_name/g" $filename
    sed -i "s/%AUTHOR_FAMILY_NAME%/$family_name/g" $filename
    sed -i "s/%PROJECT_NAME%/$project_name/g" $filename
    sed -i "s/%PROJECT_URLNAME%/$urlname/g" $filename
    sed -i "s/%PROJECT_DESCRIPTION%/$description/g" $filename
    sed -i "s/%CREATION_DATE%/$creation_date/g" $filename
    sed -i "s/%CREATION_YEAR%/$creation_year/g" $filename
    echo "Performed substitutions in $filename"
done

mv project_name $project_name
rm -f codemeta.json
mv codemeta-TEMPLATE.json codemeta.json
rm -f CITATION.cff
mv CITATION-TEMPLATE.cff CITATION.cff

# This command runs only once on GHA!
rm -rf .github/template.yml

echo "Renaming project ... Done."

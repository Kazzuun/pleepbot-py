from pydantic import BaseModel, Field, field_validator


__all__ = ("Meal",)


class Meal(BaseModel):
    id: str = Field(alias="idMeal")
    meal: str = Field(alias="strMeal")
    category: str = Field(alias="strCategory")
    area: str = Field(alias="strArea")
    instructions: str = Field(alias="strInstructions")
    picture: str = Field(alias="strMealThumb")
    tags: list[str] = Field(alias="strTags")
    youtube: str = Field(alias="strYoutube")
    source: str | None = Field(alias="strSource")

    ingredient1: str | None = Field(alias="strIngredient1")
    ingredient2: str | None = Field(alias="strIngredient2")
    ingredient3: str | None = Field(alias="strIngredient3")
    ingredient4: str | None = Field(alias="strIngredient4")
    ingredient5: str | None = Field(alias="strIngredient5")
    ingredient6: str | None = Field(alias="strIngredient6")
    ingredient7: str | None = Field(alias="strIngredient7")
    ingredient8: str | None = Field(alias="strIngredient8")
    ingredient9: str | None = Field(alias="strIngredient9")
    ingredient10: str | None = Field(alias="strIngredient10")
    ingredient11: str | None = Field(alias="strIngredient11")
    ingredient12: str | None = Field(alias="strIngredient12")
    ingredient13: str | None = Field(alias="strIngredient13")
    ingredient14: str | None = Field(alias="strIngredient14")
    ingredient15: str | None = Field(alias="strIngredient15")
    ingredient16: str | None = Field(alias="strIngredient16")
    ingredient17: str | None = Field(alias="strIngredient17")
    ingredient18: str | None = Field(alias="strIngredient18")
    ingredient19: str | None = Field(alias="strIngredient19")
    ingredient20: str | None = Field(alias="strIngredient20")

    measure1: str | None = Field(alias="strMeasure1")
    measure2: str | None = Field(alias="strMeasure2")
    measure3: str | None = Field(alias="strMeasure3")
    measure4: str | None = Field(alias="strMeasure4")
    measure5: str | None = Field(alias="strMeasure5")
    measure6: str | None = Field(alias="strMeasure6")
    measure7: str | None = Field(alias="strMeasure7")
    measure8: str | None = Field(alias="strMeasure8")
    measure9: str | None = Field(alias="strMeasure9")
    measure10: str | None = Field(alias="strMeasure10")
    measure11: str | None = Field(alias="strMeasure11")
    measure12: str | None = Field(alias="strMeasure12")
    measure13: str | None = Field(alias="strMeasure13")
    measure14: str | None = Field(alias="strMeasure14")
    measure15: str | None = Field(alias="strMeasure15")
    measure16: str | None = Field(alias="strMeasure16")
    measure17: str | None = Field(alias="strMeasure17")
    measure18: str | None = Field(alias="strMeasure18")
    measure19: str | None = Field(alias="strMeasure19")
    measure20: str | None = Field(alias="strMeasure20")

    @field_validator("youtube", mode="before")
    @classmethod
    def shorter_youtube_link(cls, youtube: str) -> str:
        yt_link = youtube.split("watch?v=")
        return f"https://youtu.be/{yt_link[-1]}"

    @field_validator("source", mode="before")
    @classmethod
    def empty_source(cls, source: str | None) -> str | None:
        if source == "":
            return None
        return source

    @field_validator("tags", mode="before")
    @classmethod
    def tags_to_list(cls, tags: str | None) -> list[str]:
        if tags is None:
            return []
        return tags.split(",")

    @property
    def ingredients(self) -> list[str]:
        ingredient_list = [
            self.ingredient1,
            self.ingredient2,
            self.ingredient3,
            self.ingredient4,
            self.ingredient5,
            self.ingredient6,
            self.ingredient7,
            self.ingredient8,
            self.ingredient9,
            self.ingredient10,
            self.ingredient11,
            self.ingredient12,
            self.ingredient13,
            self.ingredient14,
            self.ingredient15,
            self.ingredient16,
            self.ingredient17,
            self.ingredient18,
            self.ingredient19,
            self.ingredient20,
        ]
        return [
            ingredient
            for ingredient in ingredient_list
            if ingredient != "" and ingredient != " " and ingredient is not None
        ]

    @property
    def measures(self) -> list[str]:
        measure_list = [
            self.measure1,
            self.measure2,
            self.measure3,
            self.measure4,
            self.measure5,
            self.measure6,
            self.measure7,
            self.measure8,
            self.measure9,
            self.measure10,
            self.measure11,
            self.measure12,
            self.measure13,
            self.measure14,
            self.measure15,
            self.measure16,
            self.measure17,
            self.measure18,
            self.measure19,
            self.measure20,
        ]
        return [measure for measure in measure_list if measure != "" and measure != " " and measure is not None]

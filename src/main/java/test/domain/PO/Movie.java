package test.domain.PO;

import lombok.Data;
import org.neo4j.ogm.annotation.NodeEntity;
import org.neo4j.ogm.annotation.Property;
import org.neo4j.ogm.annotation.Relationship;

import java.util.ArrayList;
import java.util.List;

@Data
@NodeEntity(label = "Movie")
public class Movie extends BaseNode{

    @Property(name = "title")
    private String title;
    @Property(name = "released")
    private Long released;
    @Property(name = "tagline")
    private String tagline;

    @Relationship(type = "ACTED_IN")
    List<ACTED_IN> relationship = new ArrayList<>();
}
